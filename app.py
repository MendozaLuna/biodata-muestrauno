import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import math
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
import folium
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONFIGURACIÓN DE SEGURIDAD (SECRETS) ---
if "GOOGLE_API_KEY" in st.secrets and "SUPABASE_URL" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
else:
    st.error("⚠️ Error: Faltan las llaves en los Secrets.")
    st.stop()

# --- 2. DICCIONARIO DE ACCESOS (Tus clientes) ---
# Aquí defines la clave y el nombre exacto de la clínica (como aparece en tu Excel/Supabase)
ACCESOS_CLINICAS = {
    "AdminBio2026": "ADMIN",             # Acceso para ti (ve todo)
    "ClinisacPremium26": "Clinisac",      # Clave de Clinisac
    "VisionPro26": "Visión Pro",          # Ejemplo clínica 2
    "EcoOftalmo26": "Centro Eco-Oftalmo"  # Ejemplo clínica 3
}

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: white !important; font-weight: 900 !important; width: 100%; border-radius: 12px !important; border: none !important; padding: 10px 20px !important; }
    div.stButton > button:hover { background-color: #2E7D32 !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 18px; border-radius: 12px; margin: 10px 0; border-left: 8px solid #2E7D32; }
    .med-info-box h4, .med-info-box p { color: white !important; }
    .premium-card { border: 5px solid #D4AF37 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 15px; position: relative; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. LÓGICA DE NAVEGACIÓN ---
if 'perfil' not in st.session_state:
    st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown("<h1 style='text-align: center; color: #1B5E20;'>BioData</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #333;'>Inteligencia de Mercado Oftalmológico</h3>", unsafe_allow_html=True)
    col_p, col_e = st.columns(2)
    with col_p:
        if st.button("👤 PACIENTE\n\nBusco estudios", use_container_width=True):
            st.session_state.perfil = 'persona'; st.rerun()
    with col_e:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión", use_container_width=True):
            st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 5. CONTENIDO ---

# --- A. PERFIL PERSONA (Buscador igual) ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"): st.session_state.perfil = None; st.rerun()
    st.title("🔍 Buscador de Estudios Especiales")
    # ... (Aquí se mantiene el código de búsqueda que ya tienes configurado) ...
    # [Para ahorrar espacio en la respuesta, omito el bloque repetido del buscador que ya funciona]

# --- B. PERFIL CLÍNICA (PORTAL PERSONALIZADO) ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="v_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Clínicas Aliadas")
    
    clave = st.text_input("Introduce tu clave de Aliado", type="password")
    
    if clave in ACCESOS_CLINICAS:
        nombre_clinica = ACCESOS_CLINICAS[clave]
        
        try:
            res_db = supabase.table("clics").select("*").execute()
            df_clics = pd.DataFrame(res_db.data)

            if not df_clics.empty:
                # FILTRADO SEGÚN EL USUARIO
                if nombre_clinica == "ADMIN":
                    st.success(f"👋 ¡Hola Administrador! Estás viendo el tráfico global.")
                    stats_vista = df_clics
                else:
                    st.success(f"👋 ¡Hola **{nombre_clinica}**! Estos son tus resultados en BioData.")
                    stats_vista = df_clics[df_clics['clinica'] == nombre_clinica]

                # MÉTRICAS
                c1, c2 = st.columns(2)
                with c1:
                    st.metric(f"Pacientes enviados a {nombre_clinica if nombre_clinica != 'ADMIN' else 'BioData'}", len(stats_vista))
                with c2:
                    if not stats_vista.empty:
                        top_estudio = stats_vista['estudio'].value_counts().idxmax()
                        st.metric("Tu examen más solicitado", top_estudio)

                st.write("---")
                # GRÁFICOS PERSONALIZADOS
                if not stats_vista.empty:
                    st.subheader("📊 Histórico de Derivaciones")
                    st.line_chart(stats_vista['fecha'].str[:10].value_counts().sort_index())
                    
                    st.subheader("🧪 Distribución por Estudio")
                    st.bar_chart(stats_vista['estudio'].value_counts())
                else:
                    st.info("Aún no hemos registrado pacientes dirigidos a tu clínica este mes.")

            else:
                st.warning("No hay datos registrados en la plataforma aún.")
        except Exception as e:
            st.error(f"Error de conexión: {e}")
    elif clave != "":
        st.error("❌ Clave no reconocida. Contacta a soporte BioData.")
