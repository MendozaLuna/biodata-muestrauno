import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import math
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
import folium
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets and "SUPABASE_URL" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
else:
    st.error("⚠️ Error: Faltan las llaves en los Secrets.")
    st.stop()

# --- 2. DICCIONARIO DE ACCESOS ---
ACCESOS_CLINICAS = {
    "AdminBio2026": "ADMIN",
    "ClinisacPremium26": "Clinisac",
    "OftalmoPlus26": "Oftalmo Plus"
}

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: white !important; font-weight: 900 !important; width: 100%; border-radius: 12px !important; border: none !important; padding: 10px 20px !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 18px; border-radius: 12px; margin: 10px 0; border-left: 8px solid #2E7D32; }
    .med-info-box h4, .med-info-box p { color: white !important; margin: 0; }
    .premium-card { border: 5px solid #D4AF37 !important; border-radius: 15px; padding: 30px; background-color: #FFFDF0; margin-bottom: 10px; text-align: center; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 15px; font-size: 1.1rem; }
    .btn-share { background-color: #34B7F1 !important; color: white !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; font-size: 1.1rem; }
    </style>
