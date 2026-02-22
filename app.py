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

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.title("🔍 BioData")

with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Gemini API Key:", type="password")
    user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")

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
            
            with st.spinner('Analizando...'):
                response = model.generate_content(["Identify the medical study. Respond ONLY with the name.", img])
                detectado = response.text.strip().replace(".", "") # Quita puntos finales
                
                # BÚSQUEDA FLEXIBLE: Busca cada palabra por separado
                palabras_clave = normalizar_texto(detectado).split()
                def coincide(row_text):
                    texto_fila = normalizar_texto(row_text)
                    return all(p in texto_fila for p in palabras_clave)

                resultados = df[df['Estudio'].apply(coincide)].copy()
                
                if not resultados.empty:
                    geolocator = Nominatim(user_agent="medical_app_v2")
                    user_loc = geolocator.geocode(user_city)
                    
                    lat_base = user_loc.latitude if user_loc else 10.48
                    lon_base = user_loc.longitude if user_loc else -66.90
                    m = folium.Map(location=[lat_base, lon_base], zoom_start=12)
                    
                    if user_loc:
                        folium.Marker([lat_base, lon_base], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def procesar(row):
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

                    resultados['Km'] = resultados.apply(procesar, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio')
                    mejor = resultados.iloc[0]

                    st.success(f"✅ Estudio: {detectado}")
                    col1, col2 = st.columns([1, 1.2])
                    with col1:
                        st.subheader(f"🌟 Recomendación: {mejor['Nombre']}")
                        st.metric("Precio", f"${int(mejor['Precio'])}")
                        st.write(f"📍 {mejor['Direccion']}")
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            st.markdown(f"[💬 WhatsApp](https://wa.me/{str(int(mejor['Whatsapp']))})")
                    with col2:
                        folium_static(m)
                    
                    st.write("---")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No hay convenios para '{detectado}'. Revisa que el nombre en el Excel coincida.")
        except Exception as e:
            st.error(f"Error: {e}")                    
