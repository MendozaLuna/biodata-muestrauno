import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
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
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# 3. CSS ESTILO BIODATA
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
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; width: 100%; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIÓN MATEMÁTICA DE DISTANCIA ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    try:
        R = 6371.0 
        dlat = math.radians(float(lat2) - float(lat1))
        dlon = math.radians(float(lon2) - float(lon1))
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 1)
    except:
        return 99.0

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
u_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")

c1, c2 = st.columns(2)
with c1: 
    prio = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with c2: 
    manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: OCT, Eco...")

up_img = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not up_img and not manual:
        st.warning("⚠️ Ingresa un estudio o sube una imagen.")
    else:
        try:
            # --- CARGA DE EXCEL ---
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            df = df.dropna(subset=['Estudio', 'Precio'])

            nombre_estudio = ""
            if manual:
                nombre_estudio = manual.upper()
            else:
                # MODELO ACTUALIZADO AQUÍ
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(up_img)
                with st.spinner('Analizando imagen...'):
                    res = model.generate_content(["Identifica el examen médico. Responde solo el nombre.", img])
                    nombre_estudio = res.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # --- FILTRADO ---
            p_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            if not p_clave: p_clave = [limpiar_texto(nombre_estudio)]

            res = df[df['Estudio'].astype(str).apply(lambda x: any(p in limpiar_texto(x) for p in p_clave))].copy()

            if not res.empty:
                geo = Nominatim(user_agent="biodata_v2026_final")
                u_loc = geo.geocode(u_city)
                u_lat, u_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)

                kms, coords = [], []
                for i in range(len(res)):
                    d, c = 99.0, None
                    row = res.iloc[i]
                    direc = str(row.get('Direccion', '')).strip()
                    if direc and direc.lower() != 'nan':
                        try:
                            l = geo.geocode(direc)
                            if l:
                                d = calcular_distancia(u_lat, u_lon, l.latitude, l.longitude)
                                c = [l.latitude, l.longitude]
                        except:
                            pass
                    kms.append(d)
                    coords.append(c)

                res['Km'] = kms
                res['coords'] = coords
                res['Precio'] = pd.to_numeric(res['Precio'], errors='coerce').fillna(0)
                res = res.sort_values(by='Precio' if prio == "Precio" else 'Km')

                m_opt = res.iloc[0]
                col_i, col_m = st.columns([1, 1.5])
                
                with col_i:
                    st.markdown(f'<div class="info-card"><h3>{m_opt["Nombre"]}</h3><h1>${int(m_opt["Precio"])}</h1><p>📍 {m_opt["Km"]} km</p></div>', unsafe_allow_html=True)
                    if 'Whatsapp' in m_opt:
                        wa = str(m_opt['Whatsapp']).split('.')[0]
                        st.markdown(f'<a href="https://wa.me/{wa}" class="btn-whatsapp" target="_blank">💬 CONTACTAR</a>', unsafe_allow_html=True)

                with col_m:
                    mapa = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                    folium.Marker([u_lat, u_lon], popup="Tú", icon=folium.Icon(color='red')).add_to(mapa)
                    for _, r in res.iterrows():
                        if r['coords']: folium.Marker(r['coords'], popup=r['Nombre']).add_to(mapa)
                    folium_static(mapa)
                
                st.dataframe(res[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else:
                st.error(f"No se encontraron resultados para '{nombre_estudio}'.")
        
        except Exception as e:
            st.error(f"Error técnico: {e}")
