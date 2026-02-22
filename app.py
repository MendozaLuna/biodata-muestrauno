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

# 2. CSS DE ALTO CONTRASTE REFORZADO
st.markdown("""
    <style>
    /* Ocultar basura visual */
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    
    /* FONDO GENERAL BLANCO */
    .stApp { background-color: #FFFFFF !important; }

    /* ETIQUETAS Y TEXTOS: SIEMPRE NEGROS */
    label, p, span, h1, h2, h3, .stMarkdown {
        color: #000000 !important;
        font-weight: 700 !important;
    }

    /* RESALTADO DEL ARCHIVO CARGADO (Orden Medica 02.jpeg) */
    [data-testid="stFileUploaderFileName"] {
        color: #000000 !important;
        background-color: #FFF59D !important; /* Amarillo resaltador */
        padding: 8px !important;
        border-radius: 5px !important;
        font-weight: 900 !important;
        border: 1px solid #000000 !important;
    }

    /* BOTÓN ANALIZAR: VERDE CON TEXTO BLANCO */
    div.stButton > button {
        background-color: #2E7D32 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        font-size: 1.2rem !important;
        border-radius: 10px !important;
        height: 3.5em !important;
        width: 100% !important;
    }

    /* CAJA DE ESTUDIO DETECTADO */
    .ia-detect-box {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        font-size: 1.4rem;
        margin: 20px 0;
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

user_city = st.text_input("📍 Ingresa Tu Ubicación", "Caracas, Venezuela")

prioridad = st.radio(
    "Selecciona prioridad:",
    ("Precio (Menor a mayor)", "Ubicación (Más cercanos)"),
    horizontal=True
)

uploaded_image = st.file_uploader("Subir Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube la imagen de tu orden.")
    else:
        try:
            # 1. Cargar Datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            # 2. IA Detección
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando imagen...'):
                response = model.generate_content(["¿Qué examen médico es este? Responde solo el nombre.", img])
                detectado = response.text.strip().upper()
                
                # 3. Mostrar Detección
                st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO: {detectado}</div>', unsafe_allow_html=True)

                # 4. Filtrar Resultados
                detectado_limpio = limpiar_y_normalizar(detectado)
                palabras_ia = set(detectado_limpio.split())

                def coincide(row_text):
                    t = limpiar_y_normalizar(str(row_text))
                    return any(p in t for p in palabras_ia)

                resultados = df[df['Estudio'].apply(coincidence)].copy()

                if not resultados.empty:
                    # 5. Geolocalización y Mapa
                    geolocator = Nominatim(user_agent="biodata_final_v11")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                    folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)

                    def get_dist(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 99.9

                    resultados['Km'] = resultados.apply(get_dist, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    
                    # 6. Ordenar y Mostrar
                    criterio = 'Precio' if "Precio" in prioridad else 'Km'
                    resultados = resultados.sort_values(by=criterio)

                    st.write("---")
                    col_map, col_tab = st.columns([1.2, 1])
                    with col_map:
                        st.subheader("📍 Mapa de Sedes")
                        folium_static(m)
                    with col_tab:
                        st.subheader("📋 Precios y Distancias")
                        st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No hay sedes registradas para '{detectado}'.")

        except Exception as e:
            st.error(f"Hubo un problema: {e}")       
