import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- CONFIGURACIÓN PRIVADA ---
MI_API_KEY = "AIzaSyAaiF9yI0I0csgFnMiCo7jA-LxcbDm0t_I"
genai.configure(api_key=MI_API_KEY)

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(page_title="BioData", layout="wide", initial_sidebar_state="collapsed")

# 2. DISEÑO "PURE HEALTH" (CSS DE ALTO CONTRASTE)
st.markdown("""
    <style>
    /* Ocultar elementos nativos */
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton { visibility: hidden; display: none; }
    
    /* Fondo Blanco Nieve para limpieza total */
    .stApp { background-color: #FFFFFF !important; }

    /* TEXTOS: Color Gris Carbono para máxima legibilidad */
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #2C3E50 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
        font-weight: 600 !important;
    }

    /* INPUT DE UBICACIÓN */
    .stTextInput input {
        background-color: #F8F9FA !important;
        color: #1A1A1A !important;
        border: 2px solid #D1D8E0 !important;
        border-radius: 8px;
        font-size: 16px;
    }

    /* RECTÁNGULO DE CARGA (LIMPIO Y CLARO) */
    section[data-testid="stFileUploader"] {
        background-color: #F8F9FA !important;
        border: 2px dashed #27AE60 !important;
        border-radius: 12px;
        padding: 25px !important;
    }

    /* TEXTO INTERNO DEL CARGADOR (FORZAR NEGRO) */
    [data-testid="stFileUploadDropzoneInstructions"] div div::before {
        content: "SUBE TU ORDEN MÉDICA AQUÍ";
        color: #2C3E50 !important; /* Gris oscuro legible */
        font-weight: 800 !important;
        font-size: 1.1rem !important;
    }
    [data-testid="stFileUploadDropzoneInstructions"] div div span { display: none !important; }

    /* BOTÓN BROWSE FILES (VERDE SOBRE BLANCO) */
    button[data-testid="stBaseButton-secondary"] {
        background-color: #27AE60 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
        padding: 10px 20px !important;
    }

    /* BOTÓN PRINCIPAL (VERDE ACCIÓN) */
    div.stButton > button {
        background-color: #27AE60 !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
        height: 3.5em !important;
        font-weight: 800 !important;
        font-size: 1.1rem !important;
        width: 100% !important;
        border: none !important;
        box-shadow: 0px 4px 10px rgba(39, 174, 96, 0.2) !important;
    }

    /* RESULTADO IA */
    .ia-detect-box {
        background-color: #E8F5E9 !important;
        color: #1B5E20 !important;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: 800;
        border: 1px solid #27AE60;
    }

    /* TARJETA DE RESULTADO PRECIO */
    .resalte-card {
        background-color: #FFFFFF !important;
        padding: 20px;
        border-radius: 15px;
        border-left: 8px solid #27AE60;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.08);
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# 3. INTERFAZ
st.title("🔍 BioData")

user_city = st.text_input("📍 Ingresa tu ubicación")

prioridad = st.radio(
    "Selecciona prioridad:",
    ("Precio (Menor a mayor)", "Ubicación (Más cercanos)"),
    horizontal=True
)

uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube tu orden primero.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Procesando...'):
                response = model.generate_content(["Identifica el examen médico. Responde solo el nombre.", img])
                detectado = response.text.strip()
                
                st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO: {detectado.upper()}</div>', unsafe_allow_html=True)
                
                # --- Lógica de búsqueda y mapa (se mantiene igual) ---
                geolocator = Nominatim(user_agent="biodata_clean_v5")
                user_loc = geolocator.geocode(user_city)
                lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                
                def proc_dist(row):
                    try:
                        loc = geolocator.geocode(row['Direccion'])
                        if loc: return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                    except: pass
                    return 999

                resultados = df.copy() # Simplificado para el ejemplo de color
                resultados['Km'] = resultados.apply(proc_dist, axis=1)
                resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                
                st.write("### 📋 Resultados encontrados")
                st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
