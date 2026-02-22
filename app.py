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

# --- FUNCIONES DE APOYO ---
def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

st.set_page_config(page_title="Buscador Médico Pro", page_icon="🩺", layout="wide")
st.title("🩺 Buscador Médico: Precio + Distancia + Mapa")

with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Ingresa tu Gemini API Key:", type="password")
    user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")

uploaded_image = st.file_uploader("Sube la foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar Mejor Opción con Mapa"):
    if not api_key_user or not uploaded_image:
        st.error("⚠️ Falta la API Key o la imagen.")
    else:
        try:
            nombre_archivo = "base_clinicas.xlsx"
            df = pd.read_excel(nombre_archivo)
            df.columns = df.columns.str.strip().str.capitalize()

            genai.configure(api_key=api_key_user)
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('IA Analizando y geolocalizando...'):
                response = model.generate_content(["Identify the medical study. Respond ONLY with the name.", img])
                detectado = response.text.strip()
                
                detectado_limpio = normalizar_texto(detectado)
                resultados = df[df['Estudio'].apply(normalizar_texto).str.contains(detectado_limpio, na=False)].copy()
                
                if not resultados.empty:
                    geolocator = Nominatim(user_agent="medical_app_final")
                    user_loc = geolocator.geocode(user_city)
                    
                    # Crear Mapa base
                    m = folium.Map(location=[user_loc.latitude, user_loc.longitude] if user_loc else [10.48, -66.90], zoom_start=13)
                    if user_loc:
                        folium.Marker([user_loc.latitude, user_loc.longitude], tooltip="Tú estás aquí", icon=folium.Icon(color='red')).add_to(m)

                    def procesar_clinica(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], 
                                             popup=f"{row['Nombre']}: ${row['Precio']}",
                                             tooltip=row['Nombre']).add_to(m)
                                if user_loc:
                                    return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return None

                    resultados['Km'] = resultados.apply(procesar_clinica, axis=1)
                    resultados = resultados.sort_values(by='Precio')
                    mejor = resultados.iloc[0]

                    # --- MOSTRAR RESULTADOS ---
                    st.success(f"✅ Estudio: {detectado}")
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.subheader(f"🌟 Recomendación: {mejor['Nombre']}")
                        st.metric("Precio", f"${int(mejor['Precio'])}")
                        st.write(f"📍 {mejor['Direccion']}")
                        if 'Whatsapp' in mejor:
                            st.markdown(f"[💬 Contactar](https://wa.me/{str(int(mejor['Whatsapp']))})")
                    
                    with col2:
                        st.write("### 🗺️ Ubicación de las opciones")
                        folium_static(m) # Muestra el mapa aquí
                    
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning("No se encontraron convenios.")
        except Exception as e:
            st.error(f"Error: {e}")
