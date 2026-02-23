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

# 2. CONFIGURACIÓN DE PÁGINA Y ESTILOS UNIFICADOS
st.set_page_config(page_title="BioData", layout="wide")

st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* Texto general en negro para legibilidad */
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    /* UNIFICACIÓN DE COLOR VERDE (#1B5E20) */
    
    /* 1. Cuadro de texto (Ubicación) */
    .stTextInput div div {
        background-color: #1B5E20 !important;
        color: white !important;
        border-radius: 10px !important;
    }
    .stTextInput input { color: white !important; font-weight: 600 !important; }

    /* 2. Área de subir archivo (Drag and drop) */
    [data-testid="stFileUploader"] {
        background-color: #1B5E20 !important;
        padding: 20px !important;
        border-radius: 15px !important;
        color: white !important;
    }
    [data-testid="stFileUploader"] label { color: white !important; }
    [data-testid="stFileUploaderIcon"] { color: white !important; }
    
    /* 3. Cuadro donde carga el nombre del archivo */
    [data-testid="stFileUploaderFileName"] {
        color: #1B5E20 !important;
        background-color: #FFFFFF !important;
        font-weight: 900 !important;
        border: 2px solid #1B5E20 !important;
    }

    /* 4. Cuadro de Estudio Detectado (Success) */
    .stAlert {
        background-color: #1B5E20 !important;
        color: white !important;
        border: none !important;
    }
    .stAlert p { color: white !important; }

    /* Botón Analizar y Buscar */
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
        border-radius: 10px !important;
    }

    /* Tarjetas de Resultados */
    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
        margin-bottom: 20px;
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
            
            with st.spinner('BioData analizando...'):
                response = model.generate_content(["¿Qué examen médico es? Responde solo el nombre del estudio.", img])
                detectado = response.text.strip().upper()
                
                # Cuadro de Estudio Detectado unificado
                st.success(f"✅ ESTUDIO DETECTADO: {detectado}")

                palabras_clave = limpiar_texto(detectado).split()
                resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

                if not resultados.empty:
                    geolocator = Nominatim(user_agent="biodata_v4")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    
                    def obtener_distancia(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: return 999.0
                        return 999.0

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
                            msg = f"Hola, quiero agendar: {detectado}"
                            url_wa = f"https://wa.me/{tel}?text={msg.replace(' ', '%20')}"
                            st.markdown(f'<a href="{url_wa}" class="btn-whatsapp" target="_blank">💬 CONTACTAR POR WHATSAPP</a>', unsafe_allow_html=True)

                    with col_map:
                        folium_static(m)

                    st.write("### Otras opciones encontradas")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No hay sedes registradas para '{detectado}'.")
        except Exception as e:
            st.error(f"Error: {e}")
