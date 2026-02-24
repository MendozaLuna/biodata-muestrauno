import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import math
from geopy.geocoders import Nominatim
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
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; border-left: 10px solid #2E7D32; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; width: 100%; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIÓN MATEMÁTICA DE DISTANCIA ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    try:
        R = 6371.0 
        dlat = math.radians(float(lat2) - float(lat1))
        dlon = math.radians(float(lon2) - float(lon1))
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 1)
    except: return 99.0

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
u_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")

c1, c2 = st.columns(2)
with c1: prio = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with c2: manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: OCT, Eco...")

up_img = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not up_img and not manual:
        st.warning("⚠️ Ingresa un estudio o sube una imagen.")
    else:
        try:
            # --- CARGA ROBUSTA DE EXCEL ---
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            # Limpiar filas donde 'Estudio' o 'Precio' sean nulos
            df = df.dropna(subset=['Estudio', 'Precio'])

            nombre_estudio = ""
            if manual:
                nombre_estudio = manual.upper()
            else:
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(up_img)
                with st.spinner('Analizando imagen...'):
                    res = model.generate_content(["Identifica el examen médico. Responde solo el nombre.", img])
                    nombre_estudio = res.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # --- FILTRADO FLEXIBLE ---
            p_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            if not p_clave: p_clave = [limpiar_texto(nombre_estudio)]

            # Buscamos coincidencias en la columna 'Estudio'
