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
MI_API_KEY = "AIzaSyAaiF9yI0I0csgFnMiCo7jA-LxcbDm0t_I"
genai.configure(api_key=MI_API_KEY)

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(page_title="BioData", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS DE ALTO CONTRASTE (CORRECCIÓN DE LEGIBILIDAD)
st.markdown("""
    <style>
    /* Ocultar elementos innecesarios */
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton { visibility: hidden; display: none; }
    
    /* Fondo de la App */
    .stApp { background-color: #F1F8E9 !important; }

    /* TEXTO DE LAS ETIQUETAS (Prioridad, Ubicación, etc) */
    label, .stMarkdown p, .stRadio label {
        color: #1B5E20 !important;
        font-weight: 800 !important;
        font-size: 1.1rem !important;
    }

    /* INPUT DE UBICACIÓN: Letra negra sobre fondo blanco */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #1B5E20 !important;
        font-weight: bold !important;
    }

    /* --- RECTÁNGULO DE CARGA (BROWSE FILES) --- */
    section[data-testid="stFileUploader"] {
        background-color: #1B5E20 !important; /* Fondo oscuro para que resalte */
        border: 2px dashed #C8E6C9 !important;
        border-radius: 15px;
        padding: 20px !important;
    }

    /* FORZAR TEXTO BLANCO DENTRO DEL CARGADOR */
    [data-testid="stFileUploadDropzoneInstructions"] div div span { display: none !important; }
    [data-testid="stFileUploadDropzoneInstructions"] div div::before {
        content: "SUBE TU ORDEN MÉDICA AQUÍ";
        color: #FFFFFF !important; /* BLANCO PURO */
        font-weight: 900 !important;
        font-size: 1.2rem !important;
        letter-spacing: 1px;
    }

    /* Botón interno 'Browse files' */
    button[data-testid="stBaseButton-secondary"] {
        background-color: #FFFFFF !important;
        color: #1B5E20 !important; /* Texto verde sobre botón blanco */
        border: 2px solid #FFFFFF !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
    }

    /* --- BOTÓN ANALIZAR (VERDE BOSQUE CON LETRA BLANCA) --- */
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important; /* BLANCO PURO */
        border-radius: 12px !important;
        height: 4em !important;
        width: 100% !important;
        font-weight: 900 !important;
        font-size: 1.2rem !important;
        border: none !important;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.2) !important;
    }

    /* Cuadro de detección IA */
    .ia-detect-box {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-weight: 900;
        font-size: 1.3rem;
        border: 2px solid #C8E6C9;
    }

    /* Tarjeta de resultados */
    .resalte-card {
        background-color: #FFFFFF !important;
        padding: 25px;
        border-radius: 20px;
        border-top: 12px solid #1B5E20;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.1);
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
    "Selecciona tu prioridad para los resultados:",
    ("Precio (Menor a mayor)", "Ubicación (Más cercanos)"),
    horizontal=True
)

# Espacio para el cargador
uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube una foto de tu orden.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando...'):
                response = model.generate_content(["Identifica el examen. Responde solo el nombre.", img])
                detectado = response.text.strip()
                
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())
                
                def coincidencia(row_text):
                    texto_ex = limpiar_y_normalizar(row_text)
                    palabras_ex = set(texto_ex.split())
                    return len(palabras_ia.intersection(palabras_ex)) > 0

                resultados = df[df['Estudio'].apply(coincidencia)].copy()
                
                if not resultados.empty:
                    st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO DETECTADO: {detectado.upper()}</div>', unsafe_allow_html=True)
                    
                    geolocator = Nominatim(user_agent="biodata_final_fix")
                    user_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    
                    def proc_dist(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 999

                    resultados['Km'] = resultados.apply(proc_dist, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by=['Precio' if "Precio" in prioridad else 'Km'])

                    mejor = resultados.iloc[0]
                    st.write("---")
                    col1, col2 = st.columns([1, 1.2])
                    with col1:
                        st.markdown(f"""
                            <div class="resalte-card">
                                <h2 style='color:#1B5E20;'>{mejor['Nombre']}</h2>
                                <h1 style='color:#1B5E20; font-size:4em;'>${int(mejor['Precio'])}</h1>
                                <p>📍 A <b>{mejor['Km']} km</b></p>
                            </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        folium_static(m)
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning("No se encontraron resultados.")
        except Exception as e:
            st.error(f"Error: {e}")
