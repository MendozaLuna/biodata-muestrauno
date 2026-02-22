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

# --- CONFIGURACIÓN PRIVADA ---
MI_API_KEY = "AIzaSyD_txTEBYbfxUf4-gLNJfT7XQ5q5yViZv8"
genai.configure(api_key=MI_API_KEY)

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(
    page_title="BioData",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. DISEÑO LIMPIO
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton {
        visibility: hidden; display: none;
    }
    .block-container { padding-top: 2rem; }
    .btn-whatsapp {
        background-color: #25D366; color: white; border: none;
        padding: 12px 24px; border-radius: 8px; font-weight: bold;
        text-decoration: none; display: inline-block; margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# 3. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.sidebar.text_input("📍 Tu Ciudad:", "Caracas, Venezuela")
uploaded_image = st.file_uploader("Sube o captura la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 Analizar y Buscar"):
    if not uploaded_image:
        st.error("⚠️ Por favor toma una foto o sube la orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()

            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando estudio...'):
                response = model.generate_content(["Identifica el examen médico. Responde solo el nombre del estudio.", img])
                detectado = response.text.strip()
                
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())
                
                def coincidencia(row_text):
                    texto_ex = limpiar_y_normalizar(row_text)
                    palabras_ex = set(texto_ex.split())
                    return len(palabras_ia.intersection(palabras_ex)) > 0

                resultados = df[df['Estudio'].apply(coincidencia)].copy()
                
                if not resultados.empty:
                    st.success(f"✅ Estudio Detectado: {detectado}")
                    
                    geolocator = Nominatim(user_agent="biodata_final_app")
                    user_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    if user_loc:
                        folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def procesar_puntos(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=f"{row['Nombre']}: ${row['Precio']}").add_to(m)
                                if user_loc:
                                    return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return None

                    resultados['Km'] = resultados.apply(procesar_puntos, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio')
                    mejor = resultados.iloc[0]

                    col1, col2 = st.columns([1, 1.2])
                    with col1:
                        st.subheader(f"🌟 Recomendación: {mejor['Nombre']}")
                        st.metric("Mejor Precio", f"${int(mejor['Precio'])}")
                        if mejor['Km']: st.write(f"📍 A **{mejor['Km']} km** de ti.")
                        st.write(f"🏠 {mejor['Direccion']}")
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            ws_link = f"https://wa.me/{str(int(mejor['Whatsapp']))}"
                            st.markdown(f'<a href="{ws_link}" class="btn-whatsapp" target="_blank">💬 Contactar por WhatsApp</a>', unsafe_allow_html=True)
                    
                    with col2:
                        folium_static(m)
                    
                    st.write("---")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No encontramos convenios para '{detectado}'.")

        # --- AQUÍ CAPTURAMOS EL ERROR DE CUOTA ---
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                st.warning("⏳ Estamos procesando muchas órdenes. Por favor, espera 60 segundos antes de intentar de nuevo.")
            else:
                st.error(f"Error técnico: {e}")
