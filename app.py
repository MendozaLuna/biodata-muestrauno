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

# CSS REFORZADO PARA VISIBILIDAD TOTAL
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* Forzar texto negro en toda la app */
    label, p, h1, h2, h3, .stMarkdown {
        color: #000000 !important;
        font-weight: 800 !important;
    }

    /* Nombre de archivo resaltado (Amarillo) */
    [data-testid="stFileUploaderFileName"] {
        color: #000000 !important;
        background-color: #FFFF00 !important;
        padding: 10px !important;
        font-weight: 900 !important;
        border: 2px solid #000000 !important;
    }

    /* CUADRO DE INFORMACIÓN (Tarjeta de Clínica) */
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
    }

    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_y_normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower().replace(".", "").strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

# INTERFAZ
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, sube una foto de la orden.")
    else:
        try:
            # 1. Preparar datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            # 2. IA de Google
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando estudio médico...'):
                response = model.generate_content(["¿Qué estudio es? Solo el nombre.", img])
                detectado = response.text.strip().upper()
                st.info(f"Estudio Detectado: {detectado}")

                # 3. Lógica de búsqueda
                palabras_ia = set(limpiar_y_normalizar(detectado).split())
                def match(row_text):
                    t = limpiar_y_normalizar(str(row_text))
                    return any(p in t for p in palabras_ia)

                resultados = df[df['Estudio'].apply(match)].copy()

                if not resultados.empty:
                    # 4. Mapa y Distancias
                    geolocator = Nominatim(user_agent="biodata_v13_final")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                    folium.Marker([lat_i, lon_i], tooltip="Tú", icon=folium.Icon(color='red')).add_to(m)
                    
                    def geo_proc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 99.0

                    resultados['Km'] = resultados.apply(geo_proc, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                    
                    # 5. MOSTRAR CUADRO DE INFORMACIÓN Y MAPA
                    mejor = resultados.iloc[0]
                    col_info, col_map = st.columns([1, 1.5])
                    
                    with col_info:
                        st.markdown(f"""
                            <div class="info-card">
                                <p style='color: #1B5E20; font-size: 0.8rem; margin:0;'>OPCIÓN RECOMENDADA</p>
                                <h2 style='margin: 5px 0;'>{mejor['Nombre']}</h2>
                                <h1 style='font-size: 3.5rem; color: #1B5E20; margin:0;'>${int(mejor['Precio'])}</h1>
                                <p style='font-size: 1.1rem; margin-top:10px;'>📍 A <b>{mejor['Km']} km</b></p>
                                <p style='color: #333; font-size: 0.85rem;'>{mejor['Direccion']}</p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            num_ws = str(int(mejor['Whatsapp']))
                            st.markdown(f'<a href="https://wa.me/{num_ws}" class="btn-whatsapp" target="_blank">💬 WHATSAPP</a>', unsafe_allow_html=True)

                    with col_map:
                        folium_static(m)

                    # 6. Tabla General
                    st.write("### 📋 Otras opciones encontradas")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.error(f"No hay convenios disponibles para: {detectado}")
                    
        except Exception as e:
            st.error(f"Error crítico: {e}")
