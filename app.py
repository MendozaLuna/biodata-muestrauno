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

# --- 2. CSS DE ALTA PRECISIÓN (CORRIGE ILEGIBILIDAD) ---
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    /* Corregir inputs y labels ilegibles */
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, label { 
        color: #000000 !important; 
        font-weight: 700 !important; 
    }
    
    /* Forzar fondo claro en inputs para que se vea el texto */
    .stTextInput input {
        background-color: #F0F2F6 !important;
        color: #000000 !important;
    }

    /* Cuadro Verde de la IA - Texto Blanco Forzado */
    .med-info-box { 
        background-color: #1B5E20 !important; 
        padding: 25px; 
        border-radius: 15px; 
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }
    .med-info-box * { color: #FFFFFF !important; }

    /* Tarjetas de Resultados */
    .info-card {
        border: 3px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #FFFFFF !important;
        margin-bottom: 20px;
    }
    .premium-card {
        border: 3px solid #FFD700 !important;
        background-color: #FFFDF0 !important;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
    }

    /* Botones */
    .btn-wa {
        background-color: #25D366 !important;
        color: white !important;
        padding: 12px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 800;
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
        font-weight: 800;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# --- 3. INTERFAZ ---
st.title("🔍 BioData")
u_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
uploaded_file = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_file:
        st.warning("⚠️ Por favor, carga una imagen.")
    else:
        try:
            # Cargar Base de Datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'

            # Análisis IA
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_file)
            
            with st.spinner('⌛ BioData analizando...'):
                prompt = "Extrae: NOMBRE del estudio, DESC (qué es) y RECO (utilidad). Formato: NOMBRE: [n] DESC: [d] RECO: [r]"
                resp = model.generate_content([prompt, img]).text
                
                n_e, d_e, r_e = "NO DETECTADO", "", ""
                for line in resp.split('\n'):
                    if "NOMBRE:" in line: n_e = line.split("NOMBRE:")[1].strip().upper()
                    if "DESC:" in line: d_e = line.split("DESC:")[1].strip()
                    if "RECO:" in line: r_e = line.split("RECO:")[1].strip()

                st.markdown(f'<div class="med-info-box"><h3>✅ {n_e}</h3><p><b>¿Qué es?</b> {d_e}</p><p><b>Utilidad:</b> {r_e}</p></div>', unsafe_allow_html=True)

                # Búsqueda
                p_clave = limpiar_texto(n_e).split()
                res = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in p_clave))].copy()

                if not res.empty:
                    # Geolocalización
                    geolocator = Nominatim(user_agent="biodata_final_fix")
                    loc_user = geolocator.geocode(u_city)
                    lat_i, lon_i = (loc_user.latitude, loc_user.longitude) if loc_user else (10.48, -66.90)
                    
                    def dist(row):
                        try:
                            l = geolocator.geocode(row['Direccion'])
                            return round(geodesic((lat_i, lon_i), (l.latitude, l.longitude)).km, 1) if l else 99.0
                        except: return 99.0

                    res['Km'] = res.apply(dist, axis=1)
                    res['Precio'] = pd.to_numeric(res['Precio'], errors='coerce')
                    
                    # Filtrar SaaS
                    premium = res[res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                    basic = res[~res['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')

                    c1, c2 = st.columns([1, 1.2])

                    with c1:
                        # Sección Premium
                        if not premium.empty:
                            st.write("### ⭐ DESTACADOS")
                            for _, r in premium.iterrows():
                                wa = str(int(r['Whatsapp'])) if pd.notna(r['Whatsapp']) else ""
                                st.markdown(f'<div class="premium-card"><h3>{r["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(r["Precio"])}</h2><p>📍 {r["Direccion"]} ({r["Km"]} km)</p><a href="https://wa.me/{wa}" class="btn-wa" target="_blank">💬 AGENDAR PRIORITARIO</a></div>', unsafe_allow_html=True)

                        # Sección Opción Recomendada (Mejor Basic)
                        if not basic.empty:
                            st.write("### 📋 OPCIÓN RECOMENDADA")
                            m = basic.iloc[0]
                            wa_m = str(int(m['Whatsapp'])) if pd.notna(m['Whatsapp']) else ""
                            st.markdown(f"""
                                <div class="info-card">
                                    <h3 style="color:#000000 !important;">{m['Nombre']}</h3>
                                    <h2 style="color:#1B5E20 !important;">${int(m['Precio'])}</h2>
                                    <p style="color:#000000 !important;">📍 {m['Direccion']} ({m['Km']} km)</p>
                                    <a href="https://wa.me/{wa_m}" class="btn-wa" target="_blank">💬 CONTACTAR AHORA</a>
                                </div>
                            """, unsafe_allow_html=True)

                            # Otras opciones (Lista)
                            if len(basic) > 1:
                                st.write("### 🏥 OTRAS SEDES")
                                for _, r in basic.iloc[1:4].iterrows():
                                    st.write(f"🔹 **{r['Nombre']}**: ${int(r['Precio'])} ({r['Km']} km)")

                        # Compartir
                        txt = f"🔍 *BioData*\n✅ *Estudio:* {n_e}\n🏥 *Lugar:* {res.iloc[0]['Nombre']}\n💰 *Precio:* ${int(res.iloc[0]['Precio'])}"
                        st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(txt)}" class="btn-share" target="_blank">📲 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)

                    with c2:
                        mapa = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                        folium.Marker([lat_i, lon_i], icon=folium.Icon(color='red', icon='info-sign')).add_to(mapa)
                        for _, r in res.iterrows():
                            # Se podrían añadir marcadores de clínicas aquí
                            pass
                        folium_static(mapa)
                else:
                    st.error(f"No hay resultados para '{n_e}'.")
        except Exception as e:
            st.error(f"Error técnico: {e}")
