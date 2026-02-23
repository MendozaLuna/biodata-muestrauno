import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import datetime
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 2. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# 3. CSS ESTILO BIODATA
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; padding: 20px !important; border-radius: 15px !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; width: 100%; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .premium-card { border: 4px solid #FFD700 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")

c1, c2 = st.columns(2)
with c1: prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with c2: busqueda_manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: Oct, Eco...")

uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Sube una imagen o escribe el nombre del estudio.")
    else:
        try:
            # --- CARGA Y LIMPIEZA DE COLUMNAS ---
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            df.columns = [str(c).strip() for c in df.columns]
            
            # --- MODELO GEMINI FLASH LATEST ---
            nombre_estudio = ""
            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
            else:
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('Analizando...'):
                    response = model.generate_content(["Identifica el examen medico. Responde solo el nombre.", img])
                    nombre_estudio = response.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # --- FILTRADO ---
            palabras = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

            if not resultados.empty:
                # --- GEOLOCALIZACIÓN REFORZADA ---
                geolocator = Nominatim(user_agent="biodata_v2026_fix")
                
                # 1. Obtener coordenadas del usuario de forma ultra-segura
                u_res = geolocator.geocode(user_city)
                if u_res:
                    p_user = (float(u_res.latitude), float(u_res.longitude))
                else:
                    p_user = (10.4806, -66.9036) # Caracas coordenadas puras

                kms = []
                coords_validas = []

                # 2. Procesamiento Manual (Evita el error de "arg must be a list")
                for i in range(len(resultados)):
                    dist_final = 99.0
                    coord_final = None
                    
                    #
