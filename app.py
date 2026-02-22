import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- CONFIGURACIÓN ---
MI_API_KEY = "AIzaSyAaiF9yI0I0csgFnMiCo7jA-LxcbDm0t_I"
genai.configure(api_key=MI_API_KEY)

st.set_page_config(page_title="BioData", layout="wide")

# CSS REFORZADO PARA VISIBILIDAD
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* Textos generales */
    .stWidget label, .stMarkdown p, h1, h2, h3 {
        color: #000000 !important;
        font-weight: 800 !important;
    }

    /* Nombre de archivo resaltado */
    [data-testid="stFileUploaderFileName"] {
        color: #000000 !important;
        background-color: #FFFF00 !important;
        padding: 10px !important;
        font-weight: 900 !important;
        border: 2px solid #000000 !important;
    }

    /* TARJETA DE INFORMACIÓN (EL CUADRO QUE FALTA) */
    .info-card {
        background-color: #FFFFFF !important;
        border: 3px solid #1B5E20 !important;
        border-radius: 20px;
        padding: 25px;
        margin: 20px 0;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.1);
    }

    .btn-whatsapp {
        background-color: #25D366 !important;
        color: #FFFFFF !important;
        padding: 15px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        margin-top: 15px;
    }

    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# INTERFAZ
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")
prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube tu orden.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando...'):
                response = model.generate_content(["¿Qué estudio es? Solo el nombre.", img])
                detectado = response.text.strip().upper()
                st.success(f"Estudio detectado: {detectado}")

                # Filtrado
                palabras_ia = set(limpiar_y_normalizar(detectado).split())
                def match(row_text):
                    t = limpiar_y_normalizar(str(row_text))
                    return any(p in t for p in palabras_ia)

                resultados = df[df['Estudio'].apply(match)].copy()

                if not resultados.empty:
                    geolocator = Nominatim(user_agent="biodata_v12")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    
                    def geo_proc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 99.0

                    resultados['Km'] = resultados.apply(geo_proc, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                    
                    # --- AQUÍ VUELVE EL CUADRO DE INFORMACIÓN ---
                    mejor = resultados.iloc[0]
                    col_info, col_map
