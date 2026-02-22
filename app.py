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

st.set_page_config(page_title="BioData", layout="wide")

# 2. CSS DE ALTO CONTRASTE (REFORZADO CONTRA DESCONFIGURACIÓN)
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }

    /* Forzar que todas las etiquetas sean negras y legibles */
    .stWidget label, .stMarkdown p, .stRadio label {
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 1rem !important;
    }

    /* RESALTADO DEL ARCHIVO CARGADO (AMARILLO BRILLANTE) */
    [data-testid="stFileUploaderFileName"] {
        color: #000000 !important;
        background-color: #FFFF00 !important; /* Amarillo puro */
        padding: 10px !important;
        border-radius: 8px !important;
        font-weight: 900 !important;
        border: 2px solid #000000 !important;
    }

    /* BOTÓN ANALIZAR: VERDE BOSQUE */
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        border-radius: 10px !important;
        border: none !important;
        height: 3.5em !important;
    }

    /* CAJA DE ESTUDIO DETECTADO */
    .ia-detect-box {
        background-color: #2E7D32 !important;
        color: #FFFFFF !important;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 800;
        margin-top: 20px;
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

user_city = st.text_input("Ingresa Tu Ubicación", "Caracas, Venezuela")

prioridad = st.radio(
    "Selecciona tu prioridad para los resultados:",
    ("Precio (Menor a mayor)", "Ubicación (Más cercanos)"),
    horizontal=True
)

uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube tu orden primero.")
    else:
        try:
            # 1. Cargar Base
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            # 2. IA Detección
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando estudio...'):
                response = model.generate_content(["¿Qué examen es este? Responde solo el nombre.", img])
                detectado = response.text.strip().upper()
                
                # Mostrar resultado de IA
                st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO: {detectado}</div>', unsafe_allow_html=True)

                # 3. Filtrar Estudios
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())

                def coincidencia_func(row_text):
                    t = limpiar_y_normalizar(str(row_text))
                    return any(p in t for p in palabras_ia)

                resultados = df[df['Estudio'].apply(coincidencia_func)].copy()

                if not resultados.empty:
                    # 4. Geolocalización
                    geolocator = Nominatim(user_agent="biodata_final_fixed")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                    folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def calcular_km(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 99.0

                    resultados['Km'] = resultados.apply(calcular_km, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    
                    # 5. Ordenar
                    criterio = 'Precio' if "Precio" in prioridad else 'Km'
                    resultados = resultados.sort_values(by=criterio)

                    # 6. Mostrar Mapa y Resultados
                    st.write("---")
                    st.subheader("📍 Sedes encontradas en el mapa")
                    folium_static(m)
                    
                    st.subheader("📋 Lista de precios y distancias")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No tenemos convenios para '{detectado}'.")

        except Exception as e:
            st.error(f"Error detectado: {e}")
