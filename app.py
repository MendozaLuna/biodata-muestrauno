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

# 1. Función para limpiar texto (quita tildes, puntos y espacios extras)
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
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()

            genai.configure(api_key=api_key_user)
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando orden...'):
                response = model.generate_content(["Identifica el estudio médico de la imagen. Responde SOLO el nombre del estudio.", img])
                detectado = response.text.strip()
                
                # --- NUEVA LÓGICA DE BÚSQUEDA FLEXIBLE ---
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())
                
                # Filtramos: Si alguna palabra de la IA está en el nombre del estudio del Excel
                def coincidencia_flexible(row_text):
                    texto_excel = limpiar_y_normalizar(row_text)
                    palabras_excel = set(texto_excel.split())
                    # Si hay intersección de palabras (comparten al menos una palabra clave)
                    return len(palabras_ia.intersection(palabras_excel)) > 0

                resultados = df[df['Estudio'].apply(coincidencia_flexible)].copy()
                
                if not resultados.empty:
                    st.success(f"✅ Estudio detectado: {detectado}")
                    
                    # Geolocalización
                    geolocator = Nominatim(user_agent="biodata_app_v3")
                    user_loc = geolocator.geocode(user_city)
                    m = folium.Map(location=[user_loc.latitude, user_loc.longitude] if user_loc else [10.48, -66.90], zoom_start=12)
                    
                    if user_loc:
                        folium.Marker([user_loc.latitude, user_loc.longitude], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def calcular_datos(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=f"{row['Nombre']}: ${row['Precio']}").add_to(m)
                                if user_loc:
                                    return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return None

                    resultados['Km'] = resultados.apply(calcular_datos, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultado…
