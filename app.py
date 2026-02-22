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
st.set_page_config(
    page_title="BioData",
    page_icon="logo_biodata.png", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. DISEÑO "VERDE SALUD" DE ALTO CONTRASTE (CSS)
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton {
        visibility: hidden; display: none;
    }
    .stApp { background-color: #F1F8E9 !important; }
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #1B5E20 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #2E7D32 !important;
        border-radius: 10px;
        font-weight: 600;
    }
    section[data-testid="stFileUploader"] {
        background-color: #FFFFFF !important;
        border: 2px dashed #1B5E20 !important;
        border-radius: 15px;
    }
    [data-testid="stFileUploadDropzoneInstructions"] div div span { display: none; }
    [data-testid="stFileUploadDropzoneInstructions"] div div::before {
        content: "SUBE TU ORDEN AQUÍ";
        color: #1B5E20 !important;
        font-weight: 800;
    }
    button[data-testid="stBaseButton-secondary"] {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        border-radius: 12px;
        height: 4em;
        width: 100%;
        font-weight: 900;
        text-transform: uppercase;
        box-shadow: 0px 6px 20px rgba(27, 94, 32, 0.3);
    }
    .resalte-card {
        background-color: #FFFFFF !important;
        padding: 25px;
        border-radius: 20px;
        border-top: 12px solid #1B5E20;
        box-shadow: 0px 12px 40px rgba(0,0,0,0.1);
    }
    .btn-whatsapp {
        background-color: #2E7D32 !important;
        color: #FFFFFF !important;
        text-align: center;
        padding: 18px;
        border-radius: 14px;
        display: block;
        text-decoration: none;
        font-weight: 800;
    }
    .ia-detect-box {
        background-color: #1B5E20 !important; 
        color: #FFFFFF !important; 
        padding: 18px; 
        border-radius: 15px; 
        margin: 20px 0;
        text-align: center;
        font-weight: 800;
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

user_city = st.text_input("Ingresa Tu Ubicacion")

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
                    # LÍNEA CORREGIDA (Sin error de f-string)
                    st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO: {detectado.upper()}</div>', unsafe_allow_html=True)
                    
                    geolocator = Nominatim(user_agent="biodata_final_fix")
                    user_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    if user_loc:
                        folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def procesar_distancia(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=f"{row['Nombre']}").add_to(m)
                                if user_loc:
                                    return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 999

                    resultados['Km'] = resultados.apply(procesar_distancia, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')

                    if "Precio" in prioridad:
                        resultados = resultados.sort_values(by=['Precio', 'Km'])
                    else:
                        resultados = resultados.sort_values(by=['Km', 'Precio'])

                    mejor = resultados.iloc[0]

                    st.write("---")
                    col1, col2 = st.columns([1, 1.2])
                    
                    with col1:
                        etiqueta = "MEJOR PRECIO" if "Precio" in prioridad else "MÁS CERCANO"
                        st.markdown(f"""
                            <div class="resalte-card">
                                <p style='color:#1B5E20; font-size:1em; font-weight:900; margin-bottom:5px;'>{etiqueta}</p>
                                <h2 style='margin-top:0; color:#1B5E20;'>{mejor['Nombre']}</h2>
                                <h1 style='color:#1B5E20; margin:0; font-size:4em; font-weight:900;'>${int(mejor['Precio'])}</h1>
                                <div style='margin-top:20px; border-top: 2px solid #F1F8E9; padding-top:15px;'>
                                    <p style='font-size:1.1em;'>📍 A solo <b>{mejor['Km']} km</b></p>
                                    <p style='font-size:0.95em; color:#33691E;'>🏠 {mejor['Direccion']}</p>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            ws_link = f"https://wa.me/{str(int(mejor['Whatsapp']))}"
                            st.markdown(f'<a href="{ws_link}" class="btn-whatsapp" target="_blank">💬 CONTACTAR POR WHATSAPP</a>', unsafe_allow_html=True)
                    
                    with col2:
                        folium_static(m)
                    
                    st.write("### 📋 Resultados Detallados")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No encontramos resultados para '{detectado}'.")

        except Exception as e:
            st.error(f"Error: {e}")
