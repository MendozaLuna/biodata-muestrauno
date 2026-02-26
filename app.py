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

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }
    
    /* LOGO Y SLOGAN */
    .main-logo { color: #00796B; font-size: 5rem; font-weight: 800; text-align: center; margin-bottom: -15px; letter-spacing: -3px; line-height: 1; }
    .slogan-new { color: #37474F; font-size: 1.5rem; text-align: center; font-weight: 400; margin-bottom: 40px; }

    /* TARJETAS */
    .premium-card { border: 2px solid #D4AF37 !important; border-radius: 20px; padding: 20px; background-color: #FFFDF0; text-align: center; box-shadow: 0 4px 15px rgba(212,175,55,0.1); }
    .pro-card { border: 1px solid #00796B !important; border-radius: 20px; padding: 20px; background-color: #FFFFFF; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    .standard-card { border: 1px solid #CFD8DC !important; border-radius: 20px; padding: 20px; background-color: #F9F9F9; text-align: center; }

    /* BOTONES */
    div.stButton > button { background-color: #00796B !important; color: white !important; font-weight: 700 !important; border-radius: 50px !important; border: none !important; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 12px; text-align: center; border-radius: 50px; text-decoration: none; display: block; font-weight: 800; margin-top: 10px; }
    .btn-share { background-color: #F1F3F4 !important; color: #5F6368 !important; padding: 10px; text-align: center; border-radius: 50px; text-decoration: none; display: block; font-weight: 600; margin-top: 8px; border: 1px solid #E0E0E0; }

    /* BLOQUE IA */
    .med-info-box { background: linear-gradient(135deg, #00796B 0%, #26A69A 100%) !important; padding: 15px; border-radius: 15px; color: white !important; margin-bottom: 15px; }
    .med-info-box h4, .med-info-box p { color: white !important; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCIONES (SIN CAMBIOS) ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

@st.cache_data(show_spinner=False)
def generar_copy_oferta(estudio, precio):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    prompt = f"Escribe un copy publicitario corto y persuasivo para Instagram/WhatsApp de una clínica oftalmológica. Oferta: {estudio} por solo ${precio}. Incluye emojis y un llamado a la acción claro."
    res = model.generate_content(prompt)
    return res.text

@st.cache_data(show_spinner=False)
def analizar_imagen_ai(img_bytes):
    img = PIL.Image.open(io.BytesIO(img_bytes))
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(["NOMBRE | DESCRIPCIÓN (20 palabras).", img])
    partes = res.text.split('|')
    nombre = partes[0].strip().upper()
    desc = partes[1].strip() if len(partes) > 1 else "Estudio ocular."
    return nombre, desc

def registrar_busqueda(lat, lon, estudio):
    try:
        supabase.table("busquedas_stats").insert({
            "lat": float(lat), "lon": float(lon), "estudio": str(estudio), "fecha": datetime.now().isoformat()
        }).execute()
    except: pass

def enviar_sugerencia(nombre_clinica, zona):
    try:
        supabase.table("sugerencias").insert({
            "clinica": nombre_clinica, "zona": zona, "fecha": datetime.now().isoformat()
        }).execute()
        st.success("✅ ¡Gracias! La hemos recibido.")
    except: st.error("Error al enviar sugerencia.")

# --- 5. NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown('<p class="main-logo">BioData</p>', unsafe_allow_html=True)
    st.markdown('<p class="slogan-new">Busca. Compara. Resuelve.</p>', unsafe_allow_html=True)
    
    col_p, col_e = st.columns(2)
    with col_p:
        if st.button("👤 PACIENTE\n\nBusco estudios", use_container_width=True):
            st.session_state.perfil = 'persona'; st.rerun()
    with col_e:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión", use_container_width=True):
            st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 6. PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="back_p"): st.session_state.perfil = None; st.rerun()
    st.title("🔍 Buscador de Estudios")
    
    st.markdown("### 📍 ¿Dónde te encuentras?")
    col_btn, col_txt = st.columns([1, 2])
    u_lat, u_lon = None, None
    if col_btn.button("🎯 USAR MI GPS", key="gps_btn"): st.session_state.disparar_gps = True

    if st.session_state.get('disparar_gps', False):
        loc = streamlit_js_eval(data_string="navigator.geolocation.getCurrentPosition", want_output=True, key="gps_p")
        if loc and 'coords' in loc:
            u_lat, u_lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.success("✅ GPS Listo"); st.session_state.disparar_gps = False 

    with col_txt:
        u_city = st.text_input("Tu ubicación:", "Caracas, Venezuela" if not u_lat else "Ubicación GPS Detectada", key="city_input")

    def calcular_distancia(la1, lo1, la2, lo2):
        try:
            R = 6371.0
            dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
            return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)
        except: return 99.0

    st.write("---")
    c1, c2 = st.columns(2)
    with c1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True, key="sort_radio")
    with c2: manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT...", key="exam_input")
    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"], key="img_uploader")

    if st.button("🚀 BUSCAR MEJORES OPCIONES", key="main_search"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            with st.spinner('Buscando...'):
                if manual: n_est, d_est = analizar_texto_ai(manual)
                elif up_img: n_est, d_est = analizar_imagen_ai(up_img.getvalue())
                else: st.warning("Escribe el examen."); st.stop()
            
            st.markdown(f'''<div class="med-info-box"><h4>📋 {n_est}</h4><p>{d_est}</p></div>''', unsafe_allow_html=True)
            
            geo = Nominatim(user_agent="biodata_v26_app")
            if u_lat and u_lon: c_lat, c_lon = u_lat, u_lon
            else:
                try:
                    loc_manual = geo.geocode(u_city)
                    c_lat, c_lon = (loc_manual.latitude, loc_manual.longitude) if loc_manual else (10.48, -66.90)
                except: c_lat, c_lon = 10.48, -66.90
            
            registrar_busqueda(c_lat, c_lon, n_est)
            
            def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
            palabras = [p for p in norm(n_est).split() if len(p) > 2]
            res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()
            
            if not res_df.empty:
                kms = []
                m_folium = folium.Map(location=[c_lat, c_lon], zoom_start=12)
                for _, row in res_df.iterrows():
                    d = 99.0
                    try:
                        l = geo.geocode(str(row.get('Direccion','')))
                        if l: 
                            d = calcular_distancia(c_lat, c_lon, l.latitude, l.longitude)
                            folium.Marker([l.latitude, l.longitude], tooltip=row['Nombre']).add_to(m_folium)
                    except: pass
                    kms.append(d)
                
                res_df['Km'] = kms
                res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                
                def definir_estilo(row):
                    p = str(row.get('Plan', 'Básico')).strip().capitalize()
                    if p == "Premium": return "premium-card", "💎 ALIADO PREMIUM", "#D4AF37", 1
                    if p == "Pro": return "pro-card", "✅ SEDE PRO", "#00796B", 2
                    return "standard-card", "📍 SEDE BÁSICA", "#808080", 3

                res_df['Estilo_Datos'] = res_df.apply(definir_estilo, axis=1)
                res_df['Orden_Plan'] = res_df['Estilo_Datos'].apply(lambda x: x[3])
                final = res_df.sort_values(by=['Orden_Plan', 'Precio' if prio == "Precio" else 'Km'])
                mejor = final.iloc[0]
                card_class, badge_text, badge_color, _ = mejor['Estilo_Datos']
                
                col_i, col_m = st.columns([1, 1])
                with col_i:
                    st.markdown(f"""<div class="{card_class}"><p style="color: {badge_color}; font-weight: 800; font-size: 0.8rem;">{badge_text}</p><h2 style="margin:0;">{mejor['Nombre']}</h2><h1 style="font-size:3rem; margin:10px 0;">${int(mejor['Precio'])}</h1><p style="color:#607D8B;">📍 A {mejor['Km']} km</p></div>""", unsafe_allow_html=True)
                    wa_num = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                    texto_wa = f"Saludos. Consulté su sede a través de *BioData* para realizarme el estudio: {n_est}. Muchas gracias."
                    st.markdown(f'<a href="https://wa.me/{wa_num}?text={urllib.parse.quote(texto_wa)}" target="_blank" class="btn-wa">📲 CONTACTAR</a>', unsafe_allow_html=True)
                    t_share = f"*BioData*: {mejor['Nombre']} ofrece {n_est} por ${int(mejor['Precio'])}."
                    st.markdown(f'<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(t_share)}" target="_blank" class="btn-share">🔗 COMPARTIR</a>', unsafe_allow_html=True)
                
                with col_m: folium_static(m_folium, width=500, height=400)
                
                st.write("---")
                st.write("### 🏥 Sedes:")
                st.dataframe(final[['Nombre', 'Precio', 'Km', 'Direccion', 'Plan']], use_container_width=True, hide_index=True)
            else: st.error("No se encontraron sedes.")
        except Exception as e: st.error(f"Error: {e}")

# --- 7. EMPRESA (MANTENIDO) ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Gestión")
    clave = st.text_input("Clave", type="password")
    if clave in ACCESOS_CLINICAS:
        st.success(f"Bienvenido {ACCESOS_CLINICAS[clave]}")
        # Aquí continúa el resto de tu lógica de pestañas...
