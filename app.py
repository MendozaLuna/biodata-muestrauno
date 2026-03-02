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
from supabase import create_client, Client
from datetime import datetime
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

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }
    
    .brand-title { 
        color: #004D40 !important; font-size: 5rem !important; font-weight: 800 !important; 
        letter-spacing: -2px !important; margin-bottom: 0px !important; text-align: center !important; 
    }
    .brand-slogan { 
        color: #26A69A !important; font-size: 1.5rem !important; font-weight: 400 !important; 
        margin-top: -10px !important; margin-bottom: 40px !important; text-align: center !important; 
    }
    
    div.stButton > button { 
        background: linear-gradient(135deg, #26A69A 0%, #00796B 100%) !important; 
        color: #FFFFFF !important; font-weight: 700 !important; width: 100%; 
        border-radius: 50px !important; border: none !important; padding: 12px 24px !important;
        box-shadow: 0 4px 15px rgba(38, 166, 154, 0.3) !important;
        text-transform: uppercase; letter-spacing: 0.5px; white-space: pre-line;
    }
    div.stButton > button p { color: #FFFFFF !important; font-weight: 700 !important; }
    div.stButton > button:hover { background: linear-gradient(135deg, #00897B 0%, #00695C 100%) !important; transform: translateY(-1px); }
    
    .med-info-box { 
        background: #FFFFFF !important; padding: 25px; border-radius: 20px; 
        margin: 20px 0; border-left: 8px solid #26A69A !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .premium-card { background: #FFFDF0; border: 1px solid #D4AF37 !important; border-radius: 25px; padding: 30px; text-align: center; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 14px; text-align: center; border-radius: 50px; text-decoration: none; display: block; font-weight: 700; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCIONES ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

@st.cache_data(show_spinner=False)
def analizar_imagen_ai(img_bytes):
    img = PIL.Image.open(io.BytesIO(img_bytes))
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(["NOMBRE | DESCRIPCIÓN (20 palabras).", img])
    partes = res.text.split('|')
    nombre = partes[0].strip().upper() if len(partes) > 0 else "ESTUDIO"
    desc = partes[1].strip() if len(partes) > 1 else "Estudio ocular."
    return nombre, desc

def calcular_distancia(la1, lo1, la2, lo2):
    try:
        R = 6371.0
        dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
        return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)
    except: return 99.0

# --- 5. LÓGICA DE NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown('<h1 class="brand-title">BioData</h1>', unsafe_allow_html=True)
    st.markdown('<p class="brand-slogan">Busca. Compara. Resuelve.</p>', unsafe_allow_html=True)
    
    col_p, col_e = st.columns(2)
    with col_p:
        if st.button("👤 PACIENTE\n\nBusco estudios", use_container_width=True):
            st.session_state.perfil = 'persona'
            st.rerun()
    with col_e:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión", use_container_width=True):
            st.session_state.perfil = 'empresa'
            st.rerun()
    
    # --- BLOQUE DE MAPA REFORZADO (DENTRO DEL HOME) ---
    st.markdown("---")
    st.markdown("<h3 style='text-align: center; color: #00796B;'>📍 Nuestra Red de Sedes Aliadas</h3>", unsafe_allow_html=True)

    @st.cache_data(ttl=300)
    def cargar_mapa_red():
        try: 
            url_airtable = "https://airtable.com/shrkUgws0Pj2Z06Kk/download/csv"
            return pd.read_csv(url_airtable)
        except: 
            return None

    df_sedes = cargar_mapa_red()
    if df_sedes is None or df_sedes.empty:
        df_sedes = pd.DataFrame([{'Latitud': 10.48, 'Longitud': -66.90, 'Nombre de la Clinica': 'Sede Principal BioData'}])

    m_red = folium.Map(location=[10.485, -66.890], zoom_start=12)
    for i, row in df_sedes.iterrows():
        try:
            folium.Marker(
                location=[float(row['Latitud']), float(row['Longitud'])], 
                popup=f"<b>{row.get('Nombre de la Clinica', 'Sede')}</b>",
                icon=folium.Icon(color='cadetblue', icon='hospital', prefix='fa')
            ).add_to(m_red)
        except: continue
    
    col_map_espacio_izq, col_map_centro, col_map_espacio_der = st.columns([1, 10, 1])
    
    with col_map_centro:
        folium_static(m_red, width=1000, height=450)
    st.stop()

# --- 6. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver"): 
        st.session_state.perfil = None
        st.rerun()
    
    st.title("🔍 Buscador de Estudios")
    u_city = st.text_input("Tu ubicación:", "Caracas, Venezuela")
    manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")
    up_img = st.file_uploader("O sube foto de la orden", type=["jpg", "png"])

    if st.button("🚀 BUSCAR MEJORES OPCIONES"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            if manual: n_est, d_est = analizar_texto_ai(manual)
            elif up_img: n_est, d_est = analizar_imagen_ai(up_img.getvalue())
            else: st.stop()
            
            st.markdown(f'''<div class="med-info-box"><h4>📋 {n_est}</h4><p>{d_est}</p></div>''', unsafe_allow_html=True)
            
            def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
            palabras = [p for p in norm(n_est).split() if len(p) > 2]
            res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()
            
            if not res_df.empty:
                res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                final = res_df.sort_values(by='Precio')
                mejor = final.iloc[0]
                
                st.markdown(f"""
                    <div class="premium-card">
                        <h2>{mejor['Nombre']}</h2>
                        <h1>${int(mejor['Precio'])}</h1>
                        <p>📍 {mejor.get('Direccion', 'Consultar dirección')}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                wa = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                st.markdown(f'<a href="https://wa.me/{wa}" class="btn-wa">📱 CONTACTAR</a>', unsafe_allow_html=True)
            else:
                st.error("No se encontraron sedes para este estudio.")
        except Exception as e: st.error(f"Error: {e}")

# --- 7. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"): 
        st.session_state.perfil = None
        st.rerun()
    
    st.title("🏥 Portal de Gestión")
    clave = st.text_input("Clave de Acceso", type="password")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        
        eq_sel = st.selectbox("Equipo:", ["OCT", "Campímetro", "Ecógrafo"], key="eq_inv")
        est_sel = st.radio("Estatus:", ["Operativo", "En Mantenimiento"])
        
        if st.button("Guardar"):
            try:
                supabase.table("inventario_equipos").insert({
                    "clinica": nombre_c, "equipo": eq_sel, "estado": est_sel, 
                    "ultima_actualizacion": datetime.now().isoformat()
                }).execute()
                st.success("✅ Guardado."); time.sleep(1); st.rerun()
            except: st.error("Error al conectar con la base de datos.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: 12px;'>BioData 2026 - Busca. Compara. Resuelve.</p>", unsafe_allow_html=True)
