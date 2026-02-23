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
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; width: 100%; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .premium-card { border: 4px solid #FFD700 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIÓN MATEMÁTICA DE DISTANCIA ---
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
with c1: prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with c2: busqueda_manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: Oct, Eco...")

uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Sube una imagen o escribe el nombre del estudio.")
    else:
        try:
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            df.columns = [str(c).strip() for c in df.columns]
            
            # --- MODELO GEMINI FLASH LATEST ---
            nombre_estudio = ""
            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
            else:
                model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('Analizando...'):
                    response = model.generate_content(["Identifica el examen medico. Responde solo el nombre.", img])
                    nombre_estudio = response.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            palabras = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

            if not resultados.empty:
                geolocator = Nominatim(user_agent="biodata_fix_v2026")
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
                
                p_col = 'Precio' if 'Precio' in resultados.columns else 'Precio '
                resultados['P_Num'] = pd.to_numeric(resultados[p_col], errors='coerce').fillna(0)
                
                if 'Nivel' not in resultados.columns: resultados['Nivel'] = 'Basic'
                premium = resultados[resultados['Nivel'].str.contains('Premium', case=False, na=False)].sort_values('P_Num')
                basic = resultados[~resultados['Nivel'].str.contains('Premium', case=False, na=False)].sort_values('P_Num' if prioridad == "Precio" else 'Km')
                
                col_info, col_map = st.columns([1, 1.5])
                with col_info:
                    st.info(f"📅 Verificado: {datetime.date.today().strftime('%d/%m/%Y')}")
                    for _, r in premium.iterrows():
                        wa = str(r.get('Whatsapp', '')).split('.')[0]
                        # LINEA CORREGIDA AQUÍ:
                        st.markdown(f'<div class="premium-card"><b>💎 PREMIUM</b><h3>{r["Nombre"]}</h3><h2>${int(r["P_Num"])}</h2><p>📍 {r["Km"]} km</p><a href="https://wa.me/{wa}" class="btn-whatsapp" target="_blank">💬 AGENDAR</a></div>', unsafe_allow_html=True)
                    
                    if not basic.empty:
                        m = basic.iloc[0]
                        wa_m = str(m.get('Whatsapp', '')).split('.')[0]
                        st.markdown(f'<div class="info-card"><h3>{m["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(m["P_Num"])}</h2><p>📍 {m["Km"]} km</p><a href="https://wa.me/{wa_m}" class="btn-whatsapp" target="_blank">💬 CONSULTAR</a></div>', unsafe_allow_html=True)

                with col_map:
                    mapa = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                    folium.Marker([u_lat, u_lon], popup="Tú", icon=folium.Icon(color='red')).add_to(mapa)
                    for _, r in resultados.iterrows():
                        if r['coords']:
                            folium.Marker(r['coords'], popup=f"{r['Nombre']}").add_to(mapa)
                    folium_static(mapa)
                
                st.dataframe(resultados[['Nombre', p_col, 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else:
                st.error("No se encontraron sedes.")
        except Exception as e:
            st.error(f"Error técnico: {e}")
