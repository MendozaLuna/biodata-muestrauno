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

# Función para limpiar texto y que la búsqueda no falle por acentos o puntos
def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.title("🔍 BioData")

with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Gemini API Key:", type="password")
    user_city = st.text_input("📍 Tu ubicación actual:", "Caracas, Venezuela")

uploaded_image = st.file_uploader("Sube la foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar en BioData"):
    if not api_key_user or not uploaded_image:
        st.error("⚠️ Falta la API Key o la imagen.")
    else:
        try:
            # Cargar base de datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()

            # IA analiza la imagen
            genai.configure(api_key=api_key_user)
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando...'):
                response = model.generate_content(["Identifica el estudio médico. Responde solo el nombre.", img])
                detectado = response.text.strip()
                
                # Lógica de búsqueda flexible por palabras clave
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())
                
                def coincidencia_flexible(row_text):
                    texto_excel = limpiar_y_normalizar(row_text)
                    palabras_excel = set(texto_excel.split())
                    return len(palabras_ia.intersection(palabras_excel)) > 0

                resultados = df[df['Estudio'].apply(coincidencia_flexible)].copy()
                
                if not resultados.empty:
                    st.success(f"✅ Estudio detectado: {detectado}")
                    
                    # Preparar Mapa
                    geolocator = Nominatim(user_agent="biodata_vfinal")
                    user_loc = geolocator.geocode(user_city)
                    lat_i = user_loc.latitude if user_loc else 10.48
                    lon_i = user_loc.longitude if user_loc else -66.90
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                    
                    if user_loc:
                        folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def procesar_distancia(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], 
                                             popup=f"{row['Nombre']}: ${row['Precio']}").add_to(m)
                                if user_loc:
                                    return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return None

                    resultados['Km'] = resultados.apply(procesar_distancia, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio')
                    mejor = resultados.iloc[0]

                    # Mostrar información principal
                    col1, col2 = st.columns([1, 1.2])
                    with col1:
                        st.subheader(f"🌟 Recomendación: {mejor['Nombre']}")
                        st.metric("Precio", f"${int(mejor['Precio'])}")
                        st.write(f"📍 {mejor['Direccion']}")
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            st.markdown(f"[💬 Contactar por WhatsApp](https://wa.me/{str(int(mejor['Whatsapp']))})")
                    
                    with col2:
                        folium_static(m)
                    
                    st.write("---")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No encontré coincidencias para '{detectado}'.")
        except Exception as e:
            st.error(f"Error técnico: {e}")
