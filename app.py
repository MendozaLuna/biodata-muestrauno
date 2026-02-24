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

# 2. CONFIGURACIÓN DE PÁGINA (ICONO 🔍)
st.set_page_config(
    page_title="BioData", 
    page_icon="🔍", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- TRUCO DE COMPATIBILIDAD DE ICONO PARA MÓVIL ---
st.markdown(
    """
    <head>
    <link rel="shortcut icon" href="https://cdn-icons-png.flaticon.com/512/3024/3024645.png">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3024/3024645.png">
    </head>
    """,
    unsafe_allow_html=True
)

# 3. CSS PARA ESTÉTICA UNIFICADA
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    /* Inputs en Verde BioData */
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }

    [data-testid="stFileUploader"] {
        background-color: #1B5E20 !important;
        padding: 20px !important;
        border-radius: 15px !important;
    }
    [data-testid="stFileUploader"] label, [data-testid="stFileUploaderIcon"] { color: white !important; }
    
    [data-testid="stFileUploaderFileName"] {
        color: #1B5E20 !important;
        background-color: #FFFFFF !important;
        font-weight: 900 !important;
        border: 2px solid #1B5E20 !important;
    }

    /* Cuadro de Información Médica */
    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }
    .med-info-box h3, .med-info-box p, .med-info-box b {
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }
    .med-info-box h3 { font-weight: 900 !important; margin-top: 0; }

    /* Botones */
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
        font-size: 1.1rem;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip())
                  if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Opción para subir la orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, sube una foto de la orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('🔍 BioData está analizando tu orden médica... Por favor espera.'):
                prompt = """
                Analiza esta orden médica:
                1. Nombre del estudio (una sola línea corta).
                2. Descripción breve (qué es el estudio).
                3. Recomendación (para qué sirve o qué detecta).
                Formato exacto:
                NOMBRE: [nombre]
                DESC: [descripción]
                RECO: [recomendación]
                """
                response = model.generate_content([prompt, img])
                raw_text = response.text
                
                nombre_estudio, desc_estudio, reco_estudio = "DESCONOCIDO", "", ""
                for line in raw_text.split('\n'):
                    if line.startswith("NOMBRE:"): nombre_estudio = line.replace("NOMBRE:", "").strip().upper()
                    if line.startswith("DESC:"): desc_estudio = line.replace("DESC:", "").strip()
                    if line.startswith("RECO:"): reco_estudio = line.replace("RECO:", "").strip()

                st.markdown(f"""
                    <div class="med-info-box">
                        <h3>✅ {nombre_estudio}</h3>
                        <p><b>¿Qué es?</b> {desc_estudio}</p>
                        <p><b>Utilidad Médica:</b> {reco_estudio}</p>
                    </div>
                """, unsafe_allow_html=True)

                # Filtrado
                palabras_clave = limpiar_texto(nombre_estudio).split()
                resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

                if not resultados.empty:
                    geolocator = Nominatim(user_agent="biodata_v6")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    
                    def geo_calc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 99.0

                    resultados['Km'] = resultados.apply(geo_calc, axis=1)
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
                        
                        # Botón 1: Contactar Clínica
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            tel = str(int(mejor['Whatsapp']))
                            msg_clinica = f"Hola, deseo agendar una cita para {nombre_estudio}. Vengo de BioData."
                            url_wa_clinica = f"https://wa.me/{tel}?text={msg_clinica.replace(' ', '%20')}"
                            st.markdown(f'<a href="{url_wa_clinica}" class="btn-whatsapp" target="_blank">💬 CONTACTAR CLÍNICA</a>', unsafe_allow_html=True)

                        # Botón 2: Compartir con Familiar (Azul)
                        msg_compartir = f"BioData - Resultado 🔍%0A✅ Estudio: {nombre_estudio}%0A🏥 Lugar: {mejor['Nombre']}%0A💰 Precio: ${int(mejor['Precio'])}%0A📍 Distancia: {mejor['Km']} km"
                        url_wa_share = f"https://wa.me/?text={msg_compartir}"
                        st.markdown(f'<a href="{url_wa_share}" class="btn-whatsapp" style="background-color: #34B7F1 !important;" target="_blank">📲 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)

                    with col_map:
                        folium_static(m)

                    st.write("### 📋 Otras opciones")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No hay sedes para '{nombre_estudio}'.")
        except Exception as e:
            st.error(f"Error: {e}")                  
