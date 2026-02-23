import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE SEGURIDAD (SECRETS) ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configuración incompleta: Agrega 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 2. CONFIGURACIÓN VISUAL DE LA PÁGINA
st.set_page_config(page_title="BioData", layout="wide", initial_sidebar_state="collapsed")

# 3. CSS DE ALTO CONTRASTE Y DISEÑO SEGURO
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* Forzar texto negro legible */
    label, p, h1, h2, h3, span, .stMarkdown {
        color: #000000 !important;
        font-weight: 800 !important;
    }

    /* Resaltado del nombre del archivo cargado */
    [data-testid="stFileUploaderFileName"] {
        color: #000000 !important;
        background-color: #FFFF00 !important;
        padding: 10px !important;
        font-weight: 900 !important;
        border: 2px solid #000000 !important;
        border-radius: 8px !important;
    }

    /* Tarjeta de Información de la Clínica */
    .info-card {
        background-color: #FFFFFF !important;
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0px 8px 20px rgba(0,0,0,0.1);
    }

    /* Botón de WhatsApp */
    .btn-whatsapp {
        background-color: #25D366 !important;
        color: #FFFFFF !important;
        padding: 12px;
        text-align: center;
        border-radius: 8px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        margin-top: 10px;
        transition: 0.3s;
    }
    .btn-whatsapp:hover { background-color: #128C7E !important; }

    /* Botón Principal Analizar */
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        border-radius: 10px !important;
    }
    
    .ia-detect-box {
        background-color: #2E7D32 !important;
        color: #FFFFFF !important;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 800;
        margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ DE USUARIO
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)

uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, sube una foto de la orden médica.")
    else:
        try:
            # Cargar Base de Datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            # IA - Análisis de Imagen
            model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando estudio...'):
                response = model.generate_content(["¿Qué estudio médico es este? Responde solo el nombre.", img])
                detectado = response.text.strip().upper()
                st.markdown(f'<div class="ia-detect-box">✅ ESTUDIO DETECTADO: {detectado}</div>', unsafe_allow_html=True)

                # Lógica de búsqueda en Excel
                palabras_ia = set(limpiar_y_normalizar(detectado).split())
                def match_func(row_text):
                    t = limpiar_y_normalizar(str(row_text))
                    return any(p in t for p in palabras_ia)

                resultados = df[df['Estudio'].apply(match_func)].copy()

                if not resultados.empty:
                    # Geolocalización
                    geolocator = Nominatim(user_agent="biodata_secure_app")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)
                    
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
                    
                    # 5. RESULTADOS VISUALES
                    mejor = resultados.iloc[0]
                    col_info, col_map = st.columns([1, 1.5])
                    
                    with col_info:
                        st.markdown(f"""
                            <div class="info-card">
                                <p style='color: #1B5E20; font-size: 0.8rem; margin:0;'>OPCIÓN RECOMENDADA</p>
                                <h2 style='margin: 5px 0;'>{mejor['Nombre']}</h2>
                                <h1 style='font-size: 3.5rem; color: #1B5E20; margin:0;'>${int(mejor['Precio'])}</h1>
                                <p style='font-size: 1.1rem; margin-top:10px;'>📍 A solo <b>{mejor['Km']} km</b></p>
                                <p style='color: #333; font-size: 0.85rem;'>{mejor['Direccion']}</p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            ws_num = str(int(mejor['Whatsapp']))
                            # Mensaje automático opcional
                            msg = f"Hola, vengo de BioData. Me gustaría agendar una cita para {detectado}."
                            ws_link = f"https://wa.me/{ws_num}?text={msg.replace(' ', '%20')}"
                            st.markdown(f'<a href="{ws_link}" class="btn-whatsapp" target="_blank">💬 CONTACTAR POR WHATSAPP</a>', unsafe_allow_html=True)

                    with col_map:
                        folium_static(m)

                    st.write("### 📋 Otras opciones de la red")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No encontramos sedes disponibles para: {detectado}")
                    
        except Exception as e:
            st.error(f"Ocurrió un error en el sistema: {e}")
