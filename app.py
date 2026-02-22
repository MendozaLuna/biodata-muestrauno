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

# --- CONFIGURACIÓN PRIVADA ---
# API KEY Actualizada según tu solicitud
MI_API_KEY = "AIzaSyAaiF9yI0I0csgFnMiCo7jA-LxcbDm0t_I"
genai.configure(api_key=MI_API_KEY)

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(
    page_title="BioData",
    page_icon="logo_biodata.png", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. DISEÑO "VERDE SALUD" DE ALTO CONTRASTE
st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton {
        visibility: hidden; display: none;
    }
    
    /* FONDO VERDE MENTA CLARO */
    .stApp {
        background-color: #F1F8E9 !important;
    }

    /* TEXTOS GENERALES */
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #1B5E20 !important;
        font-family: 'Segoe UI', sans-serif;
    }

    /* CUADRO DE CIUDAD: Fondo blanco y texto negro nítido */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #2E7D32 !important;
        border-radius: 10px;
        font-weight: 600;
        padding: 10px;
    }

    /* RECTÁNGULO DE CARGA (FILE UPLOADER) */
    section[data-testid="stFileUploader"] {
        background-color: #FFFFFF !important;
        border: 2px dashed #1B5E20 !important;
        border-radius: 15px;
    }

    /* TEXTO DENTRO DEL RECTÁNGULO DE CARGA */
    [data-testid="stFileUploadDropzoneInstructions"] div div span {
        display: none;
    }
    [data-testid="stFileUploadDropzoneInstructions"] div div::before {
        content: "SUBE TU ORDEN AQUÍ";
        color: #1B5E20 !important;
        font-weight: 800;
        letter-spacing: 1px;
    }
    
    /* Botón 'Browse Files' nativo */
    button[data-testid="stBaseButton-secondary"] {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }

    /* BOTÓN PRINCIPAL DE ANÁLISIS */
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        border-radius: 12px;
        height: 4em;
        width: 100%;
        font-weight: 900;
        font-size: 1.1rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        border: none;
        box-shadow: 0px 6px 20px rgba(27, 94, 32, 0.3);
        transition: 0.3s;
    }
    
    div.stButton > button:hover {
        background-color: #2E7D32 !important;
        box-shadow: 0px 8px 25px rgba(27, 94, 32, 0.4);
    }

    /* TARJETA DE RESULTADOS */
    .resalte-card {
        background-color: #FFFFFF !important;
        padding: 25px;
        border-radius: 20px;
        border-top: 12px solid #1B5E20;
        box-shadow: 0px 12px 40px rgba(0,0,0,0.1);
    }

    /* BOTÓN WHATSAPP */
    .btn-whatsapp {
        background-color: #2E7D32 !important;
        color: #FFFFFF !important;
        text-align: center;
        padding: 18px;
        border-radius: 14px;
        display: block;
        text-decoration: none;
        font-weight: 800;
        font-size: 1.1em;
    }

    /* CUADRO DETECCIÓN IA */
    .ia-detect-box {
        background-color: #1B5E20 !important; 
        color: #FFFFFF !important; 
        padding: 18px; 
        border-radius: 15px; 
        margin: 20px 0;
        text-align: center;
        font-weight: 800;
        font-size: 1.2em;
        letter-spacing: 1px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# 3. INTERFAZ PRINCIPAL
st.title("🔍 BioData")

# Etiqueta actualizada según tu solicitud
user_city = st.text_input("Ingresa Tu Ubicación", "Caracas, Venezuela")

prioridad = st.radio(
    "Selecciona tu prioridad para los resultados:",
    ("Precio (Menor a mayor)", "Ubicación (Más cercanos)"),
    horizontal=True
)

uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, sube una foto de tu orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()

            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData IA analizando...'):
                response = model.generate_content(["Identifica el examen médico. Responde solo el nombre del estudio.", img])
                detectado = response.text.strip()
                
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())
                
                def coincidencia(row_text):
                    texto_ex = limpiar_y_normalizar(row_text)
                    palabras_ex = set(texto_ex.split())
                    return len(palabras_ia.intersection(palabras_ex)) > 0

                resultados = df[df['Estudio'].apply(coincidencia)].copy()
                
                if not resultados.empty:
                    st.markdown(f'<div class="ia-detect-box
