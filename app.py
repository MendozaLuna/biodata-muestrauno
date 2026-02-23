import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. SEGURIDAD Y CONFIGURACIÓN ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets.")
    st.stop()

st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# --- 2. CSS (Tu diseño con corrección de visibilidad) ---
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
    }
    .med-info-box h3, .med-info-box p { color: white !important; }

    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
        margin-bottom: 20px;
        color: black !important;
    }
    .info-card h1, .info-card h2, .info-card p { color: black !important; margin: 5px 0; }
    
    .btn-whatsapp {
        background-color: #25D366 !important;
        color: white !important;
        padding: 12px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# --- 3. INTERFAZ ---
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")
prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Sube orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y
