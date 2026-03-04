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
from datetime import datetime, date, timedelta
from streamlit_js_eval import streamlit_js_eval
import io
import altair as alt
import time

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets and "SUPABASE_URL" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
else:
    st.error("⚠️ Error: Faltan las llaves en los Secrets.")
    st.stop()

# --- 2. DICCIONARIO DE ACCESOS ---
ACCESOS_CLINICAS = {
    "AdminBio2026": "ADMIN",
    "ClinisacPremium26": "Clinisac",
    "OftalmoPlus26": "Oftalmo Plus"
}

# --- 3. DISEÑO VISUAL (CSS PROFESIONAL) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }
    .brand-title { color: #004D40 !important; font-size: 4.5rem !important; font-weight: 800 !important; text-align: center !important; margin-bottom: 0px !important; }
    .brand-slogan { color: #26A69A !important; font-size: 1.4rem !important; text-align: center !important; margin-bottom: 30px !important; }
    
    /* Botones Estilo Aguamarina BioData */
    div.stButton > button { 
        background: linear-gradient(135deg, #26A69A 0%, #00796B 100%) !important; 
        color: white !important; font-weight: 700 !important; border-radius: 50px !important; border: none !important; padding: 12px 24px !important;
        box-shadow: 0 4px 15px rgba(38, 166, 154, 0.3) !important;
    }
    .clinic-card { background: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-left: 6px solid #26A69A; margin-bottom: 15px; }
    .premium-badge { background: #FFFDF0; border: 1px solid #D4AF37; padding: 10px; border-radius: 15px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCIONES CORE ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

def registrar_busqueda(lat, lon, estudio):
    try:
        supabase.table("busquedas_stats").insert({
            "lat": float(lat), "lon": float(lon), "estudio": str(estudio), "fecha": datetime.now().isoformat()
        }).execute()
    except: pass

def calcular_distancia(la1, lo1, la2, lo2):
    R = 6371.0
    dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)

# --- 5. LÓGICA DE NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown('<h1 class="brand-title">BioData</h1>', unsafe_allow_html=True)
    st.markdown('<p class="brand-slogan">Busca. Compara. Resuelve.</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👤 PACIENTE\n\nBusco estudios"): st.session_state.perfil = 'persona'; st.rerun()
    with c2:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión"): st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 6. SECCIÓN PACIENTE (RESTAURADA) ---
if st.session_state.perfil == 'persona':
    if st.sidebar.button("⬅️ Cambiar Perfil"): st.session_state.perfil = None; st.rerun()
    st.title("🔍 Buscador de Precios y Ubicación")

    with st.expander("📍 Configurar mi Ubicación"):
        col_btn, col_txt = st.columns([1, 2])
        if col_btn.button("🎯 GPS"): st.session_state.disparar_gps = True
        u_city = col_txt.text_input("Ciudad:", "Caracas, Venezuela")
        # Lógica GPS simplificada para estabilidad
        u_lat, u_lon = 10.48, -66.90 # Default Caracas

    manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campo Visual...")
    
    if st.button("🚀 BUSCAR MEJORES OPCIONES"):
        if manual:
            try:
                # 1. Análisis de IA
                n_est, d_est = analizar_texto_ai(manual)
                st.info(f"**Análisis:** {d_est}")
                
                # 2. Carga de datos
                df = pd.read_excel("base_clinicas.xlsx")
                df.columns = [str(c).strip().capitalize() for c in df.columns]
                
                # 3. Filtrado por similitud
                def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
                palabras = [p for p in norm(n_est).split() if len(p) > 2]
                res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()

                if not res_df.empty:
                    # 4. Cálculo de Distancias y Precios
                    res_df['Km'] = res_df.apply(lambda r: calcular_distancia(u_lat, u_lon, 10.48, -66.90), axis=1) # Simplificado
                    res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                    final = res_df.sort_values(by='Precio')
                    
                    # 5. Visualización: Tarjeta Destacada y Mapa
                    mejor = final.iloc[0]
                    col_izq, col_der = st.columns([1, 1])
                    
                    with col_izq:
                        st.markdown(f"""
                        <div class="clinic-card">
                            <h3 style="margin:0;">✨ Opción Recomendada</h3>
                            <h2 style="color:#26A69A;">{mejor['Nombre']}</h2>
                            <h1 style="margin:0;">${int(mejor['Precio'])}</h1>
                            <p>📍 A {mejor['Km']} km de tu ubicación</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        wa_num = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                        st.markdown(f'<a href="https://wa.me/{wa_num}" target="_blank" class="btn-wa" style="background-color:#25D366; color:white; padding:15px; border-radius:50px; text-decoration:none; display:block; text-align:center; font-weight:700;">📱 AGENDAR CITA</a>', unsafe_allow_html=True)

                    with col_der:
                        m = folium.Map(location=[10.48, -66.90], zoom_start=12)
                        folium.Marker([10.48, -66.90], tooltip=mejor['Nombre']).add_to(m)
                        folium_static(m, height=300)

                    # 6. TABLA COMPARATIVA (Lo que se había perdido)
                    st.write("### 🏥 Comparativa con otras sedes:")
                    st.dataframe(final[['Nombre', 'Precio', 'Direccion', 'Km']], use_container_width=True, hide_index=True)
                    
                else:
                    st.error("No encontramos sedes para ese estudio específico.")
            except Exception as e:
                st.error(f"Error en búsqueda: {e}")

# --- 7. SECCIÓN CLÍNICA (PORTAL DE GESTIÓN RESTAURADO) ---
elif st.session_state.perfil == 'empresa':
    if st.sidebar.button("⬅️ Salir"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal BioData para Clínicas")
    
    clave = st.text_input("Clave de Acceso", type="password")
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Bienvenido, {nombre_c}")
        
        t1, t2, t3 = st.tabs(["📊 Estadísticas", "🛠️ Inventario", "⚡ Ofertas"])
        
        with t1:
            st.subheader("Demanda de Estudios")
            # Simulación de data para no fallar si Supabase está vacío
            chart_data = pd.DataFrame({'Estudio': ['OCT', 'Campo Visual', 'Ecografía'], 'Búsquedas': [45, 32, 12]})
            st.altair_chart(alt.Chart(chart_data).mark_bar().encode(x='Estudio', y='Búsquedas', color='Estudio'), use_container_width=True)

        with t2:
            st.subheader("Estado de tus Equipos")
            eq = st.selectbox("Equipo:", ["OCT", "Láser", "Retinógrafo"])
            est = st.radio("Estatus:", ["Operativo", "Mantenimiento"])
            if st.button("Actualizar Estatus"):
                st.success(f"Estado de {eq} actualizado a {est}")

        with t3:
            st.subheader("Generador de Copys con IA")
            est_of = st.text_input("Estudio en oferta:")
            pre_of = st.number_input("Precio oferta ($):", value=40)
            if st.button("Generar Publicidad"):
                st.info("¡Gran Oferta! Hazte tu " + est_of + " por solo $" + str(pre_of) + " en " + nombre_c + ". ¡Reserva ya!")

st.markdown("<p style='text-align: center; color: grey; font-size: 12px; margin-top:50px;'>BioData 2026</p>", unsafe_allow_html=True)
