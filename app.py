import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import urllib.parse
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

# --- 2. RESTAURACIÓN DE COLORES Y ESTÉTICA ---
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* Forzar letras blancas en el cuadro de la IA */
    .med-info-box { 
        background-color: #1B5E20 !important; 
        padding: 25px; 
        border-radius: 15px; 
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }
    .med-info-box h3, .med-info-box p, .med-info-box b, .med-info-box span { 
        color: #FFFFFF !important; 
        font-weight: 500 !important; 
    }
    .med-info-box h3 { font-weight: 900 !important; }

    /* Estilo de Tarjetas de Resultados */
    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
        margin-bottom: 20px;
    }
    .premium-card {
        border: 4px solid #FFD700 !important;
        background-color: #FFFDF0 !important;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
    }

    /* Botones Estilo BioData */
    .btn-wa {
        background-color: #25D366 !important;
        color: white !important;
        padding: 12px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        margin-top: 10px;
    }
    .btn-share {
        background-color: #34B7F1 !important;
        color: white !important;
        padding: 12px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        margin-top: 10px;
    }
    
    label, h1, h2, h4 { color: #000000 !important; font-weight: 800 !important; }
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

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube la orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'

            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('🔍 BioData está analizando tu orden...'):
                prompt = "Extrae: NOMBRE del estudio, DESC (qué es) y RECO (utilidad). Formato: NOMBRE: [n] DESC: [d] RECO: [r]"
                response = model.generate_content([prompt, img])
                raw = response.text
                
                nombre_e = "ESTUDIO NO DETECTADO"
                desc_e, reco_e = "", ""
                for line in raw.split('\n'):
                    if "NOMBRE:" in line: nombre_e = line.split("NOMBRE:")[1].strip().upper()
                    if "DESC:" in line: desc_e = line.split("DESC:")[1].strip()
                    if "RECO:" in line: reco_e = line.split("RECO:")[1].strip()

                # Mostrar información con LETRAS BLANCAS forzadas
                st.markdown(f"""
                    <div class="med-info-box">
                        <h3>✅ {nombre_e}</h3>
                        <p><b>¿Qué es?</b> {desc_e}</p>
                        <p><b>Utilidad Médica:</b> {reco_e}</p>
                    </div>
                """, unsafe_allow_html=True)

                # Búsqueda y Geo
                palabras = limpiar_texto(nombre_e).split()
                res = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

                if not res.empty:
                    geolocator = Nominatim(user_agent="biodata_final")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    def geo_calc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            return round(geodesic((lat_i, lon_i), (loc.latitude, lon_i)).km, 1) if loc else 99.0
                        except: return 99.0

                    res['Km'] = res.apply(geo_calc, axis=1)
                    res['Precio'] = pd.to_numeric(res['Precio'], errors='coerce')
                    
                    # Separación SaaS
                    premium_df = res[res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                    basic_df = res[~res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')

                    col_data, col_map = st.columns([1, 1.2])

                    with col_data:
                        # 1. MOSTRAR PREMIUM
                        if not premium_df.empty:
                            st.write("### ⭐ CENTROS DESTACADOS")
                            for _, row in premium_df.iterrows():
                                tel = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                                st.markdown(f"""
                                    <div class="premium-card">
                                        <h3 style="margin:0;">{row['Nombre']}</h3>
                                        <h2 style="color:#1B5E20; margin:0;">${int(row['Precio'])}</h2>
                                        <p>📍 {row['Direccion']} ({row['Km']} km)</p>
                                        <a href="https://wa.me/{tel}" class="btn-wa" target="_blank">💬 AGENDAR CITA</a>
                                    </div>
                                """, unsafe_allow_html=True)

                        # 2. MOSTRAR MEJOR BASIC (OPCIÓN RECOMENDADA)
                        if not basic_df.empty:
                            mejor = basic_df.iloc[0]
                            st.write("### 📋 OPCIÓN RECOMENDADA")
                            tel_b = str(int(mejor['Whatsapp'])) if pd.notna(mejor['Whatsapp']) else ""
                            st.markdown(f"""
                                <div class="info-card">
                                    <h3 style="margin:0;">{mejor['Nombre']}</h3>
                                    <h2 style="color:#1B5E20; margin:0;">${int(mejor['Precio'])}</h2>
                                    <p>📍 {mejor['Direccion']} ({mejor['Km']} km)</p>
                                    <a href="https://wa.me/{tel_b}" class="btn-wa" target="_blank">💬 CONTACTAR AHORA</a>
                                </div>
                            """, unsafe_allow_html=True)

                        # 3. BOTÓN DE COMPARTIR
                        msg = f"🔍 *BioData - Resultado*\n✅ *Estudio:* {nombre_e}\n🏥 *Lugar:* {res.iloc[0]['Nombre']}\n💰 *Precio:* ${int(res.iloc[0]['Precio'])}"
                        msg_encoded = urllib.parse.quote(msg)
                        st.markdown(f'<a href="https://wa.me/?text={msg_encoded}" class="btn-share" target="_blank">📲 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)

                    with col_map:
                        m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                        folium.Marker([lat_i, lon_i], icon=folium.Icon(color='red')).add_to(m)
                        folium_static(m)
                else:
                    st.error(f"No hay sedes para '{nombre_e}'.")
        except Exception as e:
            st.error(f"Error: {e}")
