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

# 3. CSS PARA ESTÉTICA BIODATA
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
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 1)
    except: return 99.0

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")

c1, c2 = st.columns(2)
with c1: prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with c2: busqueda_manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: OCT, Eco, Perfil...")

uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Ingresa un estudio o sube una imagen.")
    else:
        try:
            # Carga y limpieza de Excel
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            df.columns = [str(c).strip().capitalize() for c in df.columns]

            nombre_estudio, desc_estudio, reco_estudio = "", "", ""

            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
                desc_estudio = "Búsqueda manual de usuario."
                reco_estudio = "Información basada en base de datos."
            else:
                model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('Analizando...'):
                    prompt = "Analiza la orden. NOMBRE: [nombre corto], DESC: [breve], RECO: [utilidad]"
                    response = model.generate_content([prompt, img])
                    for line in response.text.split('\n'):
                        if line.startswith("NOMBRE:"): nombre_estudio = line.replace("NOMBRE:", "").strip().upper()
                        if line.startswith("DESC:"): desc_estudio = line.replace("DESC:", "").strip()
                        if line.startswith("RECO:"): reco_estudio = line.replace("RECO:", "").strip()

            st.markdown(f'<div class="med-info-box"><h3>✅ {nombre_estudio}</h3><p>{desc_estudio}</p></div>', unsafe_allow_html=True)

            # --- FILTRADO INTELIGENTE (Mejorado) ---
            # Buscamos si el nombre del estudio en el Excel contiene alguna de las palabras clave
            palabras_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            
            if not palabras_clave: # Fallback por si el nombre es muy corto (ej: OCT)
                palabras_clave = [limpiar_texto(nombre_estudio)]

            resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

            if not resultados.empty:
                geolocator = Nominatim(user_agent="biodata_app_2026")
                u_res = geolocator.geocode(user_city)
                u_lat, u_lon = (u_res.latitude, u_res.longitude) if u_res else (10.48, -66.90)

                kms, coords = [], []
                for i in range(len(resultados)):
                    d, c = 99.0, None
                    row = resultados.iloc[i]
                    direc = str(row.get('Direccion', '')).strip()
                    if direc and direc.lower() != 'nan':
                        try:
                            loc = geolocator.geocode(direc)
                            if loc:
                                d = calcular_distancia(u_lat, u_lon, loc.latitude, loc.longitude)
                                c = [loc.latitude, loc.longitude]
                        except: pass
                    kms.append(d)
                    coords.append(c)

                resultados['Km'] = kms
                resultados['coords'] = coords
                resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce').fillna(0)
                resultados = resultados.sort_values(by='Precio' if prioridad == "Precio" else 'Km')

                mejor = resultados.iloc[0]
                col_info, col_map = st.columns([1, 1.5])
                
                with col_info:
                    st.markdown(f'<div class="info-card"><h2 style="color:#1B5E20;">{mejor["Nombre"]}</h2><h1>${int(mejor["Precio"])}</h1><p>📍 A {mejor["Km"]} km</p></div>', unsafe_allow_html=True)
                    if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                        wa = str(mejor['Whatsapp']).split('.')[0]
                        st.markdown(f'<a href="https://wa.me/{wa}?text=Deseo%20cita%20para%20{nombre_estudio}" class="btn-whatsapp" target="_blank">💬 CONTACTAR</a>', unsafe_allow_html=True)

                with col_map:
                    m = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                    folium.Marker([u_lat, u_lon], popup="Tú", icon=folium.Icon(color='red')).add_to(m)
                    for _, r in resultados.iterrows():
                        if r['coords']: folium.Marker(r['coords'], popup=r['Nombre']).add_to(m)
                    folium_static(m)

                st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else:
                st.error(f"No se encontraron sedes para '{nombre_estudio}'. Revisa si el nombre en el Excel es similar.")
        except Exception as e:
            st.error(f"Error técnico: {e}")
