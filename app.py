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

# --- 2. DICCIONARIO DE ACCESOS ---
ACCESOS_CLINICAS = {
    "AdminBio2026": "ADMIN",
    "ClinisacPremium26": "Clinisac",
    "OftalmoPlus26": "Oftalmo Plus"
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
    /* Estilo para botones de descarga */
    .stDownloadButton > button { background-color: #f0f2f6 !important; color: #1B5E20 !important; border: 2px solid #1B5E20 !important; }
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

# --- A. PERFIL PERSONA ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"): st.session_state.perfil = None; st.rerun()
    # (Bloque de búsqueda omitido, se mantiene igual al anterior)

# --- B. PERFIL CLÍNICA (PORTAL CON DESCARGA) ---
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
                if nombre_clinica == "ADMIN":
                    st.success("👋 Modo Administrador: Visibilidad Global")
                    stats_vista = df_clics
                else:
                    st.success(f"👋 ¡Hola **{nombre_clinica}**! Tu rendimiento en tiempo real:")
                    stats_vista = df_clics[df_clics['clinica'] == nombre_clinica]

                # MÉTRICAS PRINCIPALES
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Total de Pacientes Derivados", len(stats_vista))
                with c2:
                    if not stats_vista.empty:
                        top_estudio = stats_vista['estudio'].value_counts().idxmax()
                        st.metric("Servicio más solicitado", top_estudio)

                st.write("---")

                if not stats_vista.empty:
                    # GRÁFICOS
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        st.subheader("📊 Tendencia de Clics")
                        stats_vista['fecha_dt'] = pd.to_datetime(stats_vista['fecha']).dt.date
                        st.line_chart(stats_vista['fecha_dt'].value_counts().sort_index())
                    
                    with col_g2:
                        st.subheader("🧪 Estudios con más Clics")
                        st.bar_chart(stats_vista['estudio'].value_counts())

                    # DETALLE DE CONSULTAS
                    st.write("---")
                    st.subheader("📝 Detalle de Consultas Recientes")
                    
                    df_detalle = stats_vista[['fecha', 'estudio']].copy()
                    df_detalle['fecha'] = pd.to_datetime(df_detalle['fecha']).dt.strftime('%d/%m/%Y %H:%M')
                    df_detalle.columns = ['Fecha y Hora', 'Examen Solicitado']
                    
                    st.dataframe(df_detalle.sort_values(by='Fecha y Hora', ascending=False), use_container_width=True, hide_index=True)

                    # --- FUNCIÓN DE DESCARGA ---
                    st.write("### 📥 Exportar Reporte")
                    csv = df_detalle.to_csv(index=False).encode('utf-8')
                    
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.download_button(
                            label="📊 Descargar Excel (CSV)",
                            data=csv,
                            file_name=f'reporte_biodata_{nombre_clinica.lower()}.csv',
                            mime='text/csv',
                        )
                    with col_d2:
                        st.info("💡 Tip: El archivo CSV se abre directamente en Excel para tus reportes mensuales.")
                else:
                    st.info("Aún no hay clics registrados para tu clínica.")
            else:
                st.warning("No hay datos en la plataforma.")
        except Exception as e:
            st.error(f"Error: {e}")
    elif clave != "":
        st.error("❌ Clave no reconocida.")
