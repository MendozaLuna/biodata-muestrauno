import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import os
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# 1. CONFIGURACIÓN DE PWA Y PÁGINA (DEBE SER LO PRIMERO)
st.set_page_config(
    page_title="BioData",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. ESTILO PARA QUE PAREZCA UNA APP NATIVA (OCULTA MENÚS DE STREAMLIT)
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# 3. FUNCIÓN DE NORMALIZACIÓN (PARA EVITAR ERRORES DE ACENTOS Y LENGUAJE)
def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")

with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Gemini API Key:", type="password")
    user_city = st.text_input("📍 Tu ubicación actual:", "Caracas, Venezuela")
    st.info("Para instalar: En Chrome usa 'Instalar App'. En Safari usa 'Compartir' -> 'Añadir a inicio'.")

uploaded_image = st.file_uploader("Sube la foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar en BioData"):
    if not api_key_user or not uploaded_image:
        st.error("⚠️ Falta la API Key o la imagen.")
    else:
        try:
            # Cargar base de datos
            nombre_archivo = "base_clinicas.xlsx"
            if not os.path.exists(nombre_archivo):
                st.error("❌ No encontré el archivo base_clinicas.xlsx")
            else:
                df = pd.read_excel(nombre_archivo)
                df.columns = df.columns.str.strip().str.capitalize()

                # IA analiza la imagen
                genai.configure(api_key=api_key_user)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                
                with st.spinner('BioData analizando orden médica...'):
                    response = model.generate_content(["Identifica el estudio médico solicitado. Responde solo el nombre del estudio en español.", img])
                    detectado = response.text.strip()
                    
                    # Búsqueda flexible por intersección de palabras
                    detectado_limpio = limpiar_y_normalizar(detectado)
                    palabras_ia = set(detectado_limpio.split())
                    
                    def coincidencia_flexible(row_text):
                        texto_excel = limpiar_y_normalizar(row_text)
                        palabras_excel = set(texto_excel.split())
                        return len(palabras_ia.intersection(palabras_excel)) > 0

                    resultados = df[df['Estudio'].apply(coincidencia_flexible)].copy()
                    
                    if not resultados.empty:
                        st.success(f"✅ Estudio detectado: {detectado}")
                        
                        # Geolocalización del usuario
                        geolocator = Nominatim(user_agent="biodata_pwa_final")
                        user_loc = geolocator.geocode(user_city)
                        
                        lat_i = user_loc.latitude if user_loc else 10.48
                        lon_i = user_loc.longitude if user_loc else -66.90
                        
                        # Crear Mapa
                        m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                        if user_loc:
                            folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red', icon='user')).add_to(m)

                        def procesar_datos(row):
                            try:
                                loc = geolocator.geocode(row['Direccion'])
                                if loc:
                                    folium.Marker(
                                        [loc.latitude, loc.longitude], 
                                        popup=f"{row['Nombre']}: ${row['Precio']}",
                                        tooltip=row['Nombre'],
                                        icon=folium.Icon(color='blue', icon='plus-sign')
                                    ).add_to(m)
                                    if user_loc:
                                        return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                            except: pass
                            return None

                        # Aplicar cálculos
                        resultados['Km'] = resultados.apply(procesar_datos, axis=1)
                        resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                        resultados = resultados.sort_values(by='Precio')
                        mejor = resultados.iloc[0]

                        # --- DISEÑO DE RESULTADOS ---
                        col_info, col_mapa = st.columns([1, 1.2])
                        
                        with col_info:
                            st.subheader(f"🌟 Recomendación: {mejor['Nombre']}")
                            st.metric("Mejor Precio", f"${int(mejor['Precio'])}")
                            if mejor['Km'] is not None:
                                st.write(f"🚶 Estás a **{mejor['Km']} km** de distancia.")
                            st.write(f"📍 **Dirección:** {mejor['Direccion']}")
                            
                            if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                                num_ws = str(int(mejor['Whatsapp']))
                                st.markdown(f"""
                                    <a href="https://wa.me/{num_ws}" target="_blank">
                                        <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; font-weight:bold;">
                                            💬 Contactar por WhatsApp
                                        </button>
                                    </a>
                                """, unsafe_allow_html=True)
                        
                        with col_mapa:
                            st.write("### 🗺️ Ubicación de Clínicas")
                            folium_static(m)
                        
                        st.write("---")
                        st.write("### 📊 Todas las opciones encontradas:")
                        st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                    else:
                        st.warning(f"No encontré coincidencias para '{detectado}'. Intenta verificar el nombre en tu Excel.")

        except Exception as e:
            st.error(f"Hubo un error al procesar: {e}")
