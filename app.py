import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 2. CONFIGURACIÓN DE PÁGINA Y ESTILOS
st.set_page_config(page_title="BioData", layout="wide")

st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    /* Input de Ubicación */
    .stTextInput div div { background-color: #1B5E20 !important; color: white !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; }

    /* Área de subir archivo */
    [data-testid="stFileUploader"] {
        background-color: #1B5E20 !important;
        padding: 20px !important;
        border-radius: 15px !important;
        color: white !important;
    }
    [data-testid="stFileUploader"] label { color: white !important; }
    
    /* Cuadro de Información Médica (Estudio Detectado) */
    .med-info-box {
        background-color: #1B5E20 !important;
        color: white !important;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }

    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
        border-radius: 10px !important;
    }

    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
    }
    
    .btn-whatsapp {
        background-color: #25D366 !important;
        color: #FFFFFF !important;
        padding: 15px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip())
                  if unicodedata.category(c) != 'Mn')

# 3. INTERFAZ
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Opción para subir la orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube la orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando estudio y generando recomendaciones...'):
                # PROMPT MEJORADO PARA DESCRIPCIÓN MÉDICA
                prompt = """
                Analiza esta orden médica:
                1. Nombre del estudio (en una sola línea corta).
                2. Descripción breve (qué es el estudio).
                3. Recomendación (para qué sirve o qué detecta).
                Devuelve el resultado en este formato exacto:
                NOMBRE: [nombre]
                DESC: [descripción]
                RECO: [recomendación]
                """
                
                response = model.generate_content([prompt, img])
                raw_text = response.text
                
                # Extraer partes
                nombre_estudio = "DESCONOCIDO"
                desc_estudio = ""
                reco_estudio = ""
                
                for line in raw_text.split('\n'):
                    if line.startswith("NOMBRE:"): nombre_estudio = line.replace("NOMBRE:", "").strip().upper()
                    if line.startswith("DESC:"): desc_estudio = line.replace("DESC:", "").strip()
                    if line.startswith("RECO:"): reco_estudio = line.replace("RECO:", "").strip()

                # --- CUADRO INFORMATIVO UNIFICADO ---
                st.markdown(f"""
                    <div class="med-info-box">
                        <h3 style="color: white; margin-top: 0;">✅ {nombre_estudio}</h3>
                        <p style="color: #E8F5E9; font-size: 1rem; font-weight: 400 !important;"><b>¿Qué es?</b> {desc_estudio}</p>
                        <p style="color: #E8F5E9; font-size: 1rem; font-weight: 400 !important;"><b>Utilidad Médica:</b> {reco_estudio}</p>
                    </div>
                """, unsafe_allow_html=True)

                # Búsqueda en base de datos
                palabras_clave = limpiar_texto(nombre_estudio).split()
                resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

                if not resultados.empty:
                    geolocator = Nominatim(user_agent="biodata_v5")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    
                    def obtener_distancia(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: return 99.0
                        return 99.0

                    resultados['Km'] = resultados.apply(obtener_distancia, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                    
                    mejor = resultados.iloc[0]
                    col_info, col_map = st.columns([1, 1.5])
                    
                    with col_info:
                        st.markdown(f"""
                            <div class="info-card">
                                <p style='margin:0; color:#1B5E20;'>OPCIÓN RECOMENDADA</p>
                                <h2 style='margin:0;'>{mejor['Nombre']}</h2>
                                <h1 style='color: #1B5E20; margin: 10px 0;'>${int(mejor['Precio'])}</h1>
                                <p>📍 Distancia: {mejor['Km']} km</p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            tel = str(int(mejor['Whatsapp']))
                            msg = f"Hola, quiero agendar: {nombre_estudio}"
                            url_wa = f"https://wa.me/{tel}?text={msg.replace(' ', '%20')}"
                            st.markdown(f'<a href="{url_wa}" class="btn-whatsapp" target="_blank">💬 CONTACTAR POR WHATSAPP</a>', unsafe_allow_html=True)

                    with col_map:
                        folium_static(m)
                    
                    st.write("### Otras opciones encontradas")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No hay sedes registradas para '{nombre_estudio}'.")
        except Exception as e:
            st.error(f"Error: {e}")
