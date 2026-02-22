import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- CONFIGURACIÓN ---
MI_API_KEY = "AIzaSyAaiF9yI0I0csgFnMiCo7jA-LxcbDm0t_I"
genai.configure(api_key=MI_API_KEY)

st.set_page_config(page_title="BioData", layout="wide", initial_sidebar_state="collapsed")

# 2. DISEÑO ACTUALIZADO (LETRA DE ARCHIVO RESALTADA)
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer, .stDeployButton { visibility: hidden; display: none; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* ESTILO PARA EL NOMBRE DEL ARCHIVO CARGADO */
    [data-testid="stFileUploaderFileName"] {
        color: #1B5E20 !important;
        font-weight: 900 !important;
        font-size: 1.1rem !important;
        background-color: #E8F5E9 !important;
        padding: 5px 10px !important;
        border-radius: 5px !important;
    }

    /* Botón Principal */
    div.stButton > button {
        background-color: #27AE60 !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
        width: 100% !important;
        border-radius: 10px !important;
        height: 3.5em !important;
    }

    .ia-detect-box {
        background-color: #E8F5E9 !important;
        color: #1B5E20 !important;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: 800;
        border: 1px solid #27AE60;
        margin-bottom: 20px;
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

user_city = st.text_input("📍 Ingresa Tu Ubicación")

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
            # CARGAR BASE DE DATOS
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            # IA DETECCIÓN
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando estudio...'):
                response = model.generate_content(["Identifica el examen médico. Responde solo el nombre del estudio.", img])
                detectado = response.text.strip()
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())

                # FILTRAR ESTUDIOS REALES
                def coincidencia(row_text):
                    texto_ex = limpiar_y_normalizar(str(row_text))
                    palabras_ex = set(texto_ex.split())
                    return len(palabras_ia.intersection(palabras_ex)) > 0

                resultados = df[df['Estudio'].apply(coincidencia)].copy()

                if not resultados.empty:
                    st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO DETECTADO: {detectado.upper()}</div>', unsafe_allow_html=True)
                    
                    # CONFIGURACIÓN DEL MAPA
                    geolocator = Nominatim(user_agent="biodata_final_v10")
                    user_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (user_loc.latitude, user_loc.longitude) if user_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                    
                    if user_loc:
                        folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def procesar_geo(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 999

                    resultados['Km'] = resultados.apply(procesar_geo, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')

                    # ORDENAR POR PRIORIDAD
                    criterio = 'Precio' if "Precio" in prioridad else 'Km'
                    resultados = resultados.sort_values(by=criterio)

                    # MOSTRAR MAPA Y TABLA
                    col1, col2 = st.columns([1.2, 1])
                    with col1:
                        st.write("### 📍 Ubicaciones Disponibles")
                        folium_static(m)
                    
                    with col2:
                        st.write("### 📋 Resultados Filtrados")
                        st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No encontramos convenios para: {detectado}")

        except Exception as e:
            st.error(f"Error de sistema: {e}")
