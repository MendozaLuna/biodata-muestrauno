import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import urllib.parse  # Para corregir los símbolos de WhatsApp
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

st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# CSS para mantener el estilo profesional y letras blancas
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; font-weight: 500 !important; }
    .premium-card { border: 3px solid #FFD700; background-color: #FFFDF0; padding: 20px; border-radius: 15px; margin-bottom: 15px; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: 700; margin-top: 10px; }
    .btn-share { background-color: #34B7F1 !important; color: white !important; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: 700; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 2. INTERFAZ
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")
prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Subir orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube la orden.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'

            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('🔍 BioData está leyendo tu orden...'):
                prompt = "Dime el nombre del estudio médico, qué es y para qué sirve. Formato: NOMBRE: [nombre] DESC: [desc] RECO: [reco]"
                response = model.generate_content([prompt, img])
                raw = response.text
                
                # Extracción mejorada
                nombre_e = "ESTUDIO NO DETECTADO"
                desc_e, reco_e = "", ""
                for line in raw.split('\n'):
                    if "NOMBRE:" in line: nombre_e = line.split("NOMBRE:")[1].strip().upper()
                    if "DESC:" in line: desc_e = line.split("DESC:")[1].strip()
                    if "RECO:" in line: reco_e = line.split("RECO:")[1].strip()

                st.markdown(f'<div class="med-info-box"><h3>✅ {nombre_e}</h3><p><b>¿Qué es?</b> {desc_e}</p><p><b>Utilidad:</b> {reco_e}</p></div>', unsafe_allow_html=True)

                # Búsqueda
                palabras = limpiar_texto(nombre_e).split()
                res = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

                if not res.empty:
                    geolocator = Nominatim(user_agent="biodata_fix")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    def geo_calc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1) if loc else 99.0
                        except: return 99.0

                    res['Km'] = res.apply(geo_calc, axis=1)
                    res['Precio'] = pd.to_numeric(res['Precio'], errors='coerce')

                    # Separar Premium de Basic
                    premium_df = res[res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                    basic_df = res[~res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')

                    col_res, col_map = st.columns([1, 1.2])

                    with col_res:
                        if not premium_df.empty:
                            st.subheader("🌟 DESTACADOS")
                            for _, row in premium_df.iterrows():
                                tel = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                                st.markdown(f'<div class="premium-card"><h3>{row["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(row["Precio"])}</h2><p>📍 {row["Direccion"]} ({row["Km"]} km)</p><a href="https://wa.me/{tel}" class="btn-wa" target="_blank">💬 AGENDAR</a></div>', unsafe_allow_html=True)
                        
                        if not basic_df.empty:
                            st.subheader("📋 OTRAS OPCIONES")
                            for _, row in basic_df.head(3).iterrows():
                                st.info(f"{row['Nombre']} - ${int(row['Precio'])} ({row['Km']} km)")

                        # --- CORRECCIÓN DE COMPARTIR (URL ENCODE) ---
                        msg_text = f"🔍 *BioData - Resultado*\n✅ *Estudio:* {nombre_e}\n🏥 *Lugar:* {res.iloc[0]['Nombre']}\n💰 *Precio:* ${int(res.iloc[0]['Precio'])}"
                        msg_encoded = urllib.parse.quote(msg_text)
                        st.markdown(f'<a href="https://wa.me/?text={msg_encoded}" class="btn-share" target="_blank">📲 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)

                    with col_map:
                        m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                        folium.Marker([lat_i, lon_i], icon=folium.Icon(color='red')).add_to(m)
                        folium_static(m)
                else:
                    st.error(f"No encontramos sedes para '{nombre_e}'. Verifica tu Excel.")
        except Exception as e:
            st.error(f"Error técnico: {e}")
