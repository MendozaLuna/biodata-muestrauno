import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import math
import urllib.parse
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
import folium
from folium.plugins import HeatMap
from supabase import create_client, Client
from datetime import datetime, date
from streamlit_js_eval import streamlit_js_eval
import io

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets and "SUPABASE_URL" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
else:
    st.error("⚠️ Error: Faltan las llaves en los Secrets.")
    st.stop()

# --- 2. ACCESOS ---
ACCESOS_CLINICAS = {"AdminBio2026": "ADMIN", "ClinisacPremium26": "Clinisac", "OftalmoPlus26": "Oftalmo Plus"}

# --- 3. DISEÑO VISUAL ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: white !important; font-weight: 900 !important; border-radius: 12px !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 18px; border-radius: 12px; margin: 10px 0; border-left: 8px solid #2E7D32; }
    .med-info-box h4, .med-info-box p { color: white !important; margin: 0; }
    .premium-card { border: 5px solid #D4AF37 !important; border-radius: 15px; padding: 25px; background-color: #FFFDF0; text-align: center; }
    .standard-card { border: 2px solid #1B5E20 !important; border-radius: 15px; padding: 25px; background-color: #F9F9F9; text-align: center; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    .suggestion-box { background-color: #E8F5E9; padding: 20px; border-radius: 15px; border: 2px dashed #1B5E20; margin-top: 30px; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCIONES ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto}. Máximo 20 palabras.")
    return texto.upper(), res.text.strip()

def registrar_busqueda(lat, lon, estudio):
    try: supabase.table("busquedas_stats").insert({"lat": float(lat), "lon": float(lon), "estudio": str(estudio), "fecha": datetime.now().isoformat()}).execute()
    except: pass

def enviar_sugerencia(nombre_clinica, zona):
    try:
        supabase.table("sugerencias").insert({"clinica": nombre_clinica, "zona": zona, "fecha": datetime.now().isoformat()}).execute()
        st.success("¡Gracias! Investigaremos esta sede de inmediato.")
    except: st.error("Error al enviar. Intenta más tarde.")

# --- 5. NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown("<h1 style='text-align: center; color: #1B5E20;'>BioData</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #333;'>Inteligencia de Mercado Oftalmológico</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("👤 PACIENTE\n\nBusco estudios", use_container_width=True): st.session_state.perfil = 'persona'; st.rerun()
    with c2:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión", use_container_width=True): st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 6. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    st.title("🔍 Buscador de Estudios")
    
    # GPS y Ubicación
    col_gps, col_city = st.columns([1, 2])
    u_lat, u_lon = None, None
    if col_gps.button("🎯 USAR GPS"): st.session_state.disparar_gps = True
    if st.session_state.get('disparar_gps', False):
        loc = streamlit_js_eval(data_string="navigator.geolocation.getCurrentPosition", want_output=True, key="gps_p")
        if loc: u_lat, u_lon = loc['coords']['latitude'], loc['coords']['longitude']
    with col_city: u_city = st.text_input("Ciudad/Zona:", "Caracas" if not u_lat else "GPS Activo")

    st.write("---")
    manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")
    
    if st.button("🚀 BUSCAR"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [c.strip().capitalize() for c in df.columns]
            n_est, d_est = analizar_texto_ai(manual)
            st.markdown(f'''<div class="med-info-box"><h4>📋 {n_est}</h4><p>{d_est}</p></div>''', unsafe_allow_html=True)
            
            # Lógica de filtrado (simplificada para el ejemplo)
            def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
            res_df = df[df['Estudio'].astype(str).apply(lambda x: norm(manual) in norm(x))].copy()

            if not res_df.empty:
                for _, row in res_df.head(3).iterrows():
                    estilo = "premium-card" if str(row.get('Plan')) == "Premium" else "standard-card"
                    st.markdown(f"""<div class="{estilo}"><h3>{row['Nombre']}</h3><h1>${row['Precio']}</h1><p>{row['Direccion']}</p></div>""", unsafe_allow_html=True)
                    st.markdown(f'<a href="https://wa.me/{row["Whatsapp"]}" class="btn-wa">Chat WhatsApp</a>', unsafe_allow_html=True)
                    st.write("")
            else:
                st.warning("No encontramos esa clínica exacta aún.")
            
            # --- SECCIÓN SUGERIR CLÍNICA ---
            st.markdown('<div class="suggestion-box">', unsafe_allow_html=True)
            st.subheader("¿No encontraste tu clínica de confianza?")
            st.write("Ayúdanos a mejorar BioData. Dinos cuál falta y la contactaremos.")
            col_s1, col_s2 = st.columns(2)
            with col_s1: s_nombre = st.text_input("Nombre de la Clínica:")
            with col_s2: s_zona = st.text_input("Zona/Ubicación:")
            if st.button("📩 ENVIAR SUGERENCIA"):
                if s_nombre and s_zona: enviar_sugerencia(s_nombre, s_zona)
                else: st.warning("Por favor llena ambos campos.")
            st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e: st.error(f"Error: {e}")

# --- 7. CONTENIDO EMPRESA (Dashboard Histórico) ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Gestión")
    clave = st.text_input("Clave de Acceso", type="password")
    if clave in ACCESOS_CLINICAS:
        st.success(f"Bienvenido: {ACCESOS_CLINICAS[clave]}")
        
        # Pestañas para organizar
        tab1, tab2 = st.tabs(["📊 Estadísticas de Búsqueda", "📩 Sugerencias de Usuarios"])
        
        with tab1:
            # Aquí va el código del Dashboard que ya tenemos (Mapa de calor, etc.)
            st.write("Datos de demanda en tiempo real...")
            
        with tab2:
            st.subheader("Clínicas que los pacientes están pidiendo")
            try:
                sug_data = supabase.table("sugerencias").select("*").execute()
                if sug_data.data:
                    st.table(pd.DataFrame(sug_data.data)[['clinica', 'zona', 'fecha']])
                else: st.info("Aún no hay sugerencias de usuarios.")
            except: st.info("Módulo de sugerencias listo para recibir datos.")
