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
st.set_page_config(
    page_title="BioData", 
    page_icon="🔍", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 3. CSS PARA ESTÉTICA BIODATA
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; padding: 20px !important; border-radius: 15px !important; }
    [data-testid="stFileUploader"] label, [data-testid="stFileUploaderIcon"] { color: white !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; border-left: 10px solid #2E7D32; }
    .med-info-box h3, .med-info-box p, .med-info-box b { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; height: 3.5em !important; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .premium-card { border: 4px solid #FFD700 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; font-size: 1.1rem; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip())
                  if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")

col_a, col_b = st.columns(2)
with col_a:
    prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with col_b:
    busqueda_manual = st.text_input("⌨️ Búsqueda manual (Opcional):", placeholder="Ej: Oct, Topografía...")

uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Sube una imagen o escribe el nombre del estudio.")
    else:
        try:
            # --- CARGA DE TODAS LAS HOJAS DEL EXCEL ---
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            
            # Limpieza de nombres de columnas
            df.columns = df.columns.str.strip()
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'
            
            nombre_estudio = ""
            
            # --- OBTENCIÓN DEL NOMBRE DEL ESTUDIO ---
            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
            else:
                model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('🔍 BioData analizando orden...'):
                    response = model.generate_content(["Extrae el nombre del estudio médico de esta imagen. Responde SOLO el nombre corto del estudio.", img])
                    nombre_estudio = response.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # --- FILTRADO FLEXIBLE ---
            pal
