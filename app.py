import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import datetime
import math
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 2. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="BioData", 
    page_icon="🔍", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 3. CSS PARA ESTÉTICA UNIFICADA
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; padding: 20px !important; border-radius: 15px !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; border-left: 10px solid #2E7D32; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; height: 3.5em !important; border-radius: 10px !important; width: 100%; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIÓN MATEMÁTICA DE DISTANCIA (HA VERSINE) ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    try:
        R = 6371.0 
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 1)
    except:
        return 99.0

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")

c1, c2 = st.columns(2)
with c1:
    prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
with c2:
    busqueda_manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: Eco abdominal, Perfil 20...")

uploaded_image = st.file_uploader("Opción para subir la orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Sube una foto de la orden o escribe el nombre del estudio.")
    else:
        try:
            # Carga de datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            nombre_estudio, desc_estudio, reco_estudio = "", "", ""
            
            # --- LÓGICA DE BÚSQUEDA (IMAGEN O TEXTO) ---
            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
                desc_estudio = "Búsqueda manual realizada por el usuario."
                reco_estudio = "Información obtenida de la base de datos de BioData."
            else:
                model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('🔍 Analizando tu orden...'):
                    prompt = "Analiza esta orden médica. Formato: NOMBRE: [nombre corto], DESC: [qué es], RECO: [para qué sirve]"
                    response = model.generate_content([prompt, img])
                    raw_text = response.text
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

            # --- FILTRADO Y GEOLOCALIZACIÓN ---
            palabras_clave = limpiar_texto(nombre_estudio).split()
            resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

            if not resultados.empty:
                geolocator = Nominatim(user_agent="biodata_final_v1")
                u_res = geolocator.geocode(user_city)
                u_lat, u_lon = (float(u_res.latitude), float(u_res.longitude)) if u_res else (10.48, -66.90)

                kms, coords = [], []
                for i in range(len(resultados)):
                    dist_f, coord_f = 99.0, None
                    row = resultados.iloc[i]
                    dir_raw = str(row.get('Direccion', '')).replace('"', '').strip()
                    
                    if dir_raw and dir_raw.lower() != 'nan':
                        try:
                            loc = geolocator.geocode(dir_raw)
                            if loc:
                                c_lat, c_lon = float(loc.latitude), float(loc.longitude)
                                dist_f = calcular_distancia(u_lat, u_lon, c_lat, c_lon)
                                coord_f = [c_lat, c_lon]
                        except: pass
                    kms.append(dist_f)
                    coords.append(coord_f)

                resultados['Km'] = kms
                resultados['coords'] = coords
                resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce').fillna(0)
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
                        tel = str(mejor['Whatsapp']).split('.')[0]
                        url_wa = f"https://wa.me/{tel}?text=Hola,%20deseo%20agendar%20{nombre_estudio}"
                        st.markdown(f'<a href="{url_wa}" class="btn-whatsapp" target="_blank">💬 CONTACTAR CLÍNICA</a>', unsafe_allow_html=True)

                with col_map:
                    m = folium.Map(location=[u_lat, u_lon], zoom_start=13)
                    folium.Marker([u_lat, u_lon], popup="Tú", icon=folium.Icon(color='red')).add_to(m)
                    for _, r in resultados.iterrows():
                        if r['coords']:
                            folium.Marker(r['coords'], popup=r['Nombre']).add_to(m)
                    folium_static(m)

                st.write("### 📋 Otras opciones")
                st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else:
                st.error(f"No hay sedes para '{nombre_estudio}'.")
        except Exception as e:
            st.error(f"Error: {e}")
