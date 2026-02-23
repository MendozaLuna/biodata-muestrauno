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

# 2. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# 3. CSS ACTUALIZADO PARA MODELO SAAS
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    /* Estilo Inputs */
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; border-radius: 15px !important; padding: 20px; }
    [data-testid="stFileUploader"] label { color: white !important; }

    /* TARJETA PREMIUM (SaaS) */
    .premium-card {
        border: 3px solid #FFD700 !important;
        background-color: #FFFDF0 !important;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
    }
    .badge-premium {
        background-color: #FFD700;
        color: #000;
        padding: 4px 10px;
        border-radius: 5px;
        font-size: 0.7rem;
        font-weight: 900;
        text-transform: uppercase;
    }

    /* Cuadro de Información Médica */
    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; font-weight: 500 !important; }

    /* Botones */
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; border-radius: 10px !important; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: 700; margin-top: 10px; }
    .btn-share { background-color: #34B7F1 !important; color: white !important; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: 700; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ
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
            
            # Asegurar columna Nivel
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'

            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('🔍 Analizando con BioData...'):
                prompt = "Analiza esta orden: 1. Nombre estudio corto. 2. Qué es. 3. Para qué sirve. Formato: NOMBRE: [n] DESC: [d] RECO: [r]"
                response = model.generate_content([prompt, img])
                raw = response.text
                
                nombre_e, desc_e, reco_e = "DESCONOCIDO", "", ""
                for line in raw.split('\n'):
                    if line.startswith("NOMBRE:"): nombre_e = line.replace("NOMBRE:", "").strip().upper()
                    if line.startswith("DESC:"): desc_e = line.replace("DESC:", "").strip()
                    if line.startswith("RECO:"): reco_e = line.replace("RECO:", "").strip()

                st.markdown(f'<div class="med-info-box"><h3>✅ {nombre_e}</h3><p><b>¿Qué es?</b> {desc_e}</p><p><b>Utilidad:</b> {reco_e}</p></div>', unsafe_allow_html=True)

                # Filtrado y Geolocalización
                palabras = limpiar_texto(nombre_e).split()
                res = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

                if not res.empty:
                    geolocator = Nominatim(user_agent="biodata_saas_v1")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    def geo_calc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1) if loc else 99.0
                        except: return 99.0

                    res['Km'] = res.apply(geo_calc, axis=1)
                    res['Precio'] = pd.to_numeric(res['Precio'], errors='coerce')

                    # --- LÓGICA SAAS: SEPARACIÓN DE NIVELES ---
                    premium_df = res[res['Nivel'].str.contains('Premium', na=False)].sort_values(by='Precio')
                    basic_df = res[~res['Nivel'].str.contains('Premium', na=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')

                    col_res, col_map = st.columns([1, 1.2])

                    with col_res:
                        # 1. MOSTRAR PREMIUM PRIMERO
                        if not premium_df.empty:
                            st.markdown("### ⭐ CENTROS DESTACADOS")
                            for _, row in premium_df.iterrows():
                                tel = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                                st.markdown(f"""
                                    <div class="premium-card">
                                        <span class="badge-premium">Verificado</span>
                                        <h3 style="margin:5px 0;">{row['Nombre']}</h3>
                                        <h2 style="color:#1B5E20; margin:0;">${int(row['Precio'])}</h2>
                                        <p style="font-size:0.9rem; font-weight:400 !important;">📍 {row['Direccion']} ({row['Km']} km)</p>
                                        <a href="https://wa.me/{tel}?text=Hola" class="btn-wa" target="_blank">💬 AGENDAR PRIORITARIO</a>
                                    </div>
                                """, unsafe_allow_html=True)
                        
                        # 2. MOSTRAR MEJOR OPCIÓN CALIDAD/PRECIO (BASIC)
                        if not basic_df.empty:
                            st.markdown("### 📋 OTRAS OPCIONES")
                            mejor_b = basic_df.iloc[0]
                            st.markdown(f"""
                                <div style="border: 2px solid #1B5E20; padding:15px; border-radius:10px; margin-bottom:10px;">
                                    <h4 style="margin:0;">{mejor_b['Nombre']}</h4>
                                    <h3 style="color:#1B5E20; margin:0;">${int(mejor_b['Precio'])}</h3>
                                    <p style="font-size:0.8rem; font-weight:400 !important;">📍 {mejor_b['Direccion']} ({mejor_b['Km']} km)</p>
                                </div>
                            """, unsafe_allow_html=True)

                        # Botón de Compartir (Universal)
                        msg_share = f"*BioData*🔍%0AEstudio: {nombre_e}%0ALugar: {res.iloc[0]['Nombre']}%0APrecio: ${int(res.iloc[0]['Precio'])}"
                        st.markdown(f'<a href="https://wa.me/?text={msg_share}" class="btn-share" target="_blank">📲 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)

                    with col_map:
                        m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                        for _, row in res.iterrows():
                            # Lógica simple de marcadores para el mapa
                            folium.Marker([lat_i, lon_i], icon=folium.Icon(color='red')).add_to(m)
                        folium_static(m)
                else:
                    st.error("No se encontraron sedes.")
        except Exception as e:
            st.error(f"Error: {e}")            
