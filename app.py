import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets.")
    st.stop()

st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS (ESTÉTICA QUE TE GUSTA) ---
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }

    [data-testid="stFileUploader"] {
        background-color: #1B5E20 !important;
        padding: 20px !important;
        border-radius: 15px !important;
    }
    [data-testid="stFileUploader"] label, [data-testid="stFileUploaderIcon"] { color: white !important; }

    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px; border-radius: 15px; margin: 20px 0; border-left: 10px solid #2E7D32;
    }
    .med-info-box h3, .med-info-box p, .med-info-box b { color: #FFFFFF !important; }

    div.stButton > button {
        background-color: #1B5E20 !important; color: #FFFFFF !important;
        font-weight: 900 !important; height: 3.5em !important; border-radius: 10px !important;
    }

    .info-card {
        border: 4px solid #1B5E20 !important; border-radius: 15px;
        padding: 20px; background-color: #F9F9F9; margin-bottom: 20px;
    }
    
    .premium-card {
        border: 4px solid #FFD700 !important; border-radius: 15px;
        padding: 20px; background-color: #FFFDF0; margin-bottom: 20px;
    }
    
    .btn-whatsapp {
        background-color: #25D366 !important; color: #FFFFFF !important;
        padding: 15px; text-align: center; border-radius: 10px;
        text-decoration: none; display: block; font-weight: 900; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# --- 3. INTERFAZ ---
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not uploaded_image:
        st.warning("⚠️ Sube la orden.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando...'):
                prompt = "NOMBRE: [estudio] DESC: [que es] RECO: [utilidad]. Formato corto."
                resp = model.generate_content([prompt, img]).text
                
                n_e = "DESCONOCIDO"
                for line in resp.split('\n'):
                    if "NOMBRE:" in line: n_e = line.split(":")[1].strip().upper()

                st.markdown(f'<div class="med-info-box"><h3>✅ {n_e}</h3><p>Análisis completado con éxito.</p></div>', unsafe_allow_html=True)

                p_clave = limpiar_texto(n_e).split()
                res = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in p_clave))].copy()

                if not res.empty:
                    geolocator = Nominatim(user_agent="biodata_fix_v2")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    def geo(row):
                        try:
                            l = geolocator.geocode(row['Direccion'])
                            return round(geodesic((lat_i, lon_i), (l.latitude, l.longitude)).km, 1) if l else 99.0
                        except: return 99.0

                    res['Km'] = res.apply(geo, axis=1)
                    res['Precio'] = pd.to_numeric(res['Precio'], errors='coerce')
                    
                    # --- LÓGICA PREMIUM ---
                    if 'Nivel' not in res.columns: res['Nivel'] = 'Basic'
                    premium = res[res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                    basic = res[~res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')

                    c1, c2 = st.columns([1, 1.2])
                    with c1:
                        # Resultados Premium
                        for _, r in premium.iterrows():
                            wa = str(int(r['Whatsapp'])) if pd.notna(r['Whatsapp']) else ""
                            st.markdown(f'<div class="premium-card"><p style="color:#B8860B;">⭐ DESTACADO</p><h3>{r["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(r["Precio"])}</h2><p>📍 {r["Km"]} km</p><a href="https://wa.me/{wa}" class="btn-whatsapp" target="_blank">💬 AGENDAR PRIORITARIO</a></div>', unsafe_allow_html=True)
                        
                        # Resultado Recomendado (Basic)
                        if not basic.empty:
                            m = basic.iloc[0]
                            wa_m = str(int(m['Whatsapp'])) if pd.notna(m['Whatsapp']) else ""
                            st.markdown(f'<div class="info-card"><h3>{m["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(m["Precio"])}</h2><p>📍 {m["Km"]} km</p><a href="https://wa.me/{wa_m}" class="btn-whatsapp" target="_blank">💬 CONTACTAR AHORA</a></div>', unsafe_allow_html=True)

                        # Botón Compartir
                        st.markdown(f'<a href="https://wa.me/?text=Resultado" class="btn-whatsapp" style="background-color:#34B7F1 !important;" target="_blank">📲 COMPARTIR</a>', unsafe_allow_html=True)

                    with c2:
                        mapa = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                        folium_static(mapa)
                else:
                    st.error("No se encontraron sedes.")
        except Exception as e:
            st.error(f"Error: {e}")
