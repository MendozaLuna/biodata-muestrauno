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

# 2. DISEÑO PROFESIONAL "FORCE LIGHT MODE"
st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton {
        visibility: hidden; display: none;
    }
    
    /* FORZAR FONDO BLANCO */
    .stApp {
        background-color: #FFFFFF !important;
    }

    /* FORZAR TEXTO OSCURO */
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #1E3A8A !important;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Ajuste de los cuadros de entrada (Ciudad) */
    .stTextInput input {
        background-color: #F8F9FA !important;
        color: #1E3A8A !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 8px;
    }

    /* Botón Principal BioData */
    div.stButton > button {
        background-color: #2563EB !important;
        color: white !important;
        border-radius: 12px;
        height: 3.5em;
        width: 100%;
        font-weight: bold;
        border: none;
        box-shadow: 0px 4px 10px rgba(37, 99, 235, 0.2);
        margin-top: 10px;
    }
    
    /* Tarjeta de Resultado */
    .resalte-card {
        background-color: #F3F4F6 !important;
        padding: 20px;
        border-radius: 15px;
        border-top: 8px solid #2563EB;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.05);
    }

    /* Botón de WhatsApp */
    .btn-whatsapp {
        background-color: #22C55E !important;
        color: white !important;
        text-align: center;
        padding: 15px;
        border-radius: 12px;
        display: block;
        text-decoration: none;
        font-weight: bold;
        margin-top: 10px;
    }

    /* Cuadro de detección IA */
    .ia-detect-box {
        background-color: #DBEAFE !important; 
        color: #1E40AF !important; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 5px solid #2563EB; 
        margin: 15px 0;
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

# Ubicación directamente en pantalla
user_city = st.text_input("📍 Tu ciudad para calcular distancias:", "Caracas, Venezuela")

uploaded_image = st.file_uploader("Sube o toma foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR PRECIOS"):
    if not uploaded_image:
        st.error("⚠️ Por favor carga una orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()

            # --- MODELO GEMINI FLASH LATEST ---
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando con BioData IA...'):
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
                    
                    geolocator = Nominatim(user_agent="biodata_final_pwa")
                    user_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    if user_loc:
                        folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

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
                                <p style='color:#6B7280; font-size:0.8em; font-weight:bold; margin-bottom:5px;'>MEJOR PRECIO</p>
                                <h2 style='margin-top:0; color:#1E3A8A;'>{mejor['Nombre']}</h2>
                                <h1 style='color:#2563EB; margin:0;'>${int(mejor['Precio'])}</h1>
                                <p style='margin-top:10px; color:#1E3A8A;'>📍 <b>{mejor['Km']} km</b> de distancia</p>
                                <p style='font-size:0.85em; color:#4B5563;'>🏠 {mejor['Direccion']}</p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            ws_link = f"https://wa.me/{str(int(mejor['Whatsapp']))}"
                            st.markdown(f'<a href="{ws_link}" class="btn-whatsapp" target="_blank">💬 Contactar por WhatsApp</a>', unsafe_allow_html=True)
                    
                    with col2:
                        folium_static(m)
                    
                    st.write("### 📋 Otras opciones")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No encontramos convenios para '{detectado}'.")

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                st.warning("⏳ Estamos procesando muchas órdenes. Espera 60 segundos.")
            else:
                st.error(f"Error técnico: {e}")
