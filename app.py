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
MI_API_KEY = "AIzaSyAMYa-czKf_Ov5Mx0gdIXLRxYzVmQc0xFw"
genai.configure(api_key=MI_API_KEY)

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(
    page_title="BioData",
    page_icon="logo_biodata.png", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. DISEÑO "VERDE SALUD" (CSS PERSONALIZADO)
st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton {
        visibility: hidden; display: none;
    }
    
    /* FONDO VERDE MENTA SUAVE */
    .stApp {
        background-color: #E8F5E9 !important;
    }

    /* TEXTOS EN VERDE BOSQUE OSCURO */
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #1B5E20 !important;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Ajuste de los cuadros de entrada (Ciudad) */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #1B5E20 !important;
        border: 1px solid #C8E6C9 !important;
        border-radius: 10px;
    }

    /* Rectángulo de Búsqueda (File Uploader) en Español */
    section[data-testid="stFileUploader"] {
        background-color: #FFFFFF !important;
        border: 2px dashed #4CAF50 !important;
        border-radius: 15px;
        padding: 10px;
    }
    
    /* Botón Principal (Verde Bosque) */
    div.stButton > button {
        background-color: #2E7D32 !important;
        color: white !important;
        border-radius: 12px;
        height: 3.5em;
        width: 100%;
        font-weight: bold;
        border: none;
        box-shadow: 0px 4px 10px rgba(46, 125, 50, 0.2);
    }
    
    /* Tarjeta de Resultado (Elegante) */
    .resalte-card {
        background-color: #FFFFFF !important;
        padding: 25px;
        border-radius: 20px;
        border-top: 10px solid #2E7D32;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.05);
    }

    /* Botón de WhatsApp */
    .btn-whatsapp {
        background-color: #43A047 !important;
        color: white !important;
        text-align: center;
        padding: 15px;
        border-radius: 12px;
        display: block;
        text-decoration: none;
        font-weight: bold;
    }

    /* Cuadro de detección IA */
    .ia-detect-box {
        background-color: #C8E6C9 !important; 
        color: #1B5E20 !important; 
        padding: 15px; 
        border-radius: 12px; 
        border-left: 6px solid #2E7D32; 
        margin: 20px 0;
        font-weight: bold;
    }

    /* TRADUCCIÓN MANUAL DE TEXTOS DE STREAMLIT (CSS Hack) */
    [data-testid="stFileUploadDropzoneInstructions"] > div > span::after {
        content: "Arrastra tu orden aquí o haz clic para subir";
        font-size: 16px;
    }
    [data-testid="stFileUploadDropzoneInstructions"] > div > span {
        display: none;
    }
    [data-testid="stFileUploadDropzoneInstructions"] > div > small::after {
        content: "Límite 200MB por archivo • JPG, JPEG, PNG";
    }
    [data-testid="stFileUploadDropzoneInstructions"] > div > small {
        display: none;
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

# Ubicación
user_city = st.text_input("📍 Tu ciudad para calcular distancias:", "Tu Ubicacion")

# Subida de archivo (El texto de arriba también en español)
uploaded_image = st.file_uploader("Sube o toma una foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR PRECIOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, carga una imagen de tu orden primero.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()

            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData IA analizando tu estudio...'):
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
                    st.markdown(f'<div class="ia-detect-box">✅ BioData detectó: {detectado}</div>', unsafe_allow_html=True)
                    
                    geolocator = Nominatim(user_agent="biodata_green_v3")
                    user_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    if user_loc:
                        folium.Marker([lat_i, lon_i], tooltip="Tú estás aquí", icon=folium.Icon(color='red')).add_to(m)

                    def procesar_puntos(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=f"{row['Nombre']}: ${row['Precio']}").add_to(m)
                                if user_loc:
                                    return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return None

                    resultados['Km'] = resultados.apply(procesar_puntos, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio')
                    mejor = resultados.iloc[0]

                    st.write("---")
                    col1, col2 = st.columns([1, 1.2])
                    
                    with col1:
                        st.markdown(f"""
                            <div class="resalte-card">
                                <p style='color:#2E7D32; font-size:0.9em; font-weight:bold; margin-bottom:5px; letter-spacing:1px;'>MEJOR PRECIO ENCONTRADO</p>
                                <h2 style='margin-top:0; color:#1B5E20;'>{mejor['Nombre']}</h2>
                                <h1 style='color:#2E7D32; margin:0; font-size:3.5em;'>${int(mejor['Precio'])}</h1>
                                <div style='margin-top:15px; border-top: 1px solid #E8F5E9; padding-top:10px;'>
                                    <p>📍 <b>{mejor['Km']} km</b> de distancia</p>
                                    <p style='font-size:0.9em; color:#4E342E;'>🏠 {mejor['Direccion']}</p>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            ws_link = f"https://wa.me/{str(int(mejor['Whatsapp']))}"
                            st.markdown(f'<a href="{ws_link}" class="btn-whatsapp" target="_blank">💬 Contactar por WhatsApp</a>', unsafe_allow_html=True)
                    
                    with col2:
                        folium_static(m)
                    
                    st.write("### 📋 Otras alternativas disponibles")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No logramos encontrar convenios para '{detectado}'.")

        except Exception as e:
            if "429" in str(e):
                st.info("⏳ Sistema ocupado. Por favor, espera 60 segundos antes de reintentar.")
            else:
                st.error(f"Nota: {e}")
