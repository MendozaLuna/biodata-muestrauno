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
from streamlit_js_eval import streamlit_js_eval

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
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: white !important; font-weight: 900 !important; width: 100%; border-radius: 12px !important; border: none !important; padding: 10px 20px !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 18px; border-radius: 12px; margin: 10px 0; border-left: 8px solid #2E7D32; }
    .med-info-box h4, .med-info-box p { color: white !important; margin: 0; }
    .premium-card { border: 5px solid #D4AF37 !important; border-radius: 15px; padding: 30px; background-color: #FFFDF0; margin-bottom: 10px; text-align: center; }
    .standard-card { border: 2px solid #1B5E20 !important; border-radius: 15px; padding: 30px; background-color: #F9F9F9; margin-bottom: 10px; text-align: center; }
    .premium-badge { background-color: #D4AF37; color: white !important; padding: 5px 15px; border-radius: 20px; font-size: 0.8rem; font-weight: 900; display: inline-block; margin-bottom: 15px; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 15px; font-size: 1.1rem; }
    .btn-share { background-color: #34B7F1 !important; color: white !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

@st.cache_data(show_spinner=False)
def analizar_imagen_ai(img_bytes):
    import io
    img = PIL.Image.open(io.BytesIO(img_bytes))
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(["Analiza esta orden médica y extrae solo el nombre del estudio solicitado. Responde: NOMBRE | DESCRIPCIÓN (20 palabras).", img])
    partes = res.text.split('|')
    nombre = partes[0].strip().upper()
    desc = partes[1].strip() if len(partes) > 1 else "Estudio ocular especializado."
    return nombre, desc

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

# --- 5. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"):
        st.session_state.perfil = None; st.rerun()

    st.title("🔍 Buscador de Estudios")
    
    # --- BLOQUE DE UBICACIÓN CORREGIDO (SIN RECTÁNGULO NEGRO) ---
    st.markdown("### 📍 ¿Dónde te encuentras?")
    
    col_gps, col_txt = st.columns([1, 2])
    u_lat, u_lon = None, None

    with col_gps:
        # Usamos el botón para disparar la ubicación
        if st.button("🎯 USAR MI GPS"):
            st.session_state.disparar_gps = True
            
        if st.session_state.get('disparar_gps', False):
            loc = streamlit_js_eval(data_string="navigator.geolocation.getCurrentPosition", want_output=True, key="get_pos")
            if loc and 'coords' in loc:
                u_lat = loc['coords']['latitude']
                u_lon = loc['coords']['longitude']
                st.success("✅ GPS Listo")

    with col_txt:
        u_city = st.text_input("Tu ubicación:", "Caracas, Venezuela" if not u_lat else "Ubicación GPS Detectada")

    def calcular_distancia(lat1, lon1, lat2, lon2):
        try:
            R = 6371.0 
            dlat = math.radians(float(lat2) - float(lat1))
            dlon = math.radians(float(lon2) - float(lon1))
            a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
            return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)
        except: return 99.0

    def limpiar_texto(t):
        if not isinstance(t, str): return ""
        return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

    st.write("---")
    
    c_op1, c_op2 = st.columns(2)
    with c_op1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True)
    with c_op2: manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")

    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"])

    if st.button("🚀 BUSCAR MEJORES OPCIONES"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            with st.spinner('Procesando...'):
                if manual:
                    nombre_estudio, desc_estudio = analizar_texto_ai(manual)
                elif up_img:
                    nombre_estudio, desc_estudio = analizar_imagen_ai(up_img.getvalue())
                else:
                    st.warning("Escribe el examen o sube una imagen."); st.stop()

            st.markdown(f'''<div class="med-info-box"><h4>📋 {nombre_estudio}</h4><p>{desc_estudio}</p></div>''', unsafe_allow_html=True)

            palabras_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in limpiar_texto(x) for k in palabras_clave))].copy()

            if not res_df.empty:
                geo = Nominatim(user_agent="biodata_geo_v26_final")
                if u_lat and u_lon:
                    c_lat, c_lon = u_lat, u_lon
                else:
                    u_loc = geo.geocode(u_city)
                    c_lat, c_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                
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
                res_df['Es_Premium'] = res_df['Plan'].astype(str).str.contains('Premium', case=False, na=False)
                res_df['Nombre_Vista'] = res_df.apply(lambda x: f"⭐ {x['Nombre']}" if x['Es_Premium'] else x['Nombre'], axis=1)
                
                final_res = res_df.sort_values(by='Precio' if prio == "Precio" else 'Km')
                mejor = final_res.iloc[0]

                col_info, col_mapa = st.columns([1, 1])
                with col_info:
                    st.markdown(f"""
                        <div class="{'premium-card' if mejor['Es_Premium'] else 'standard-card'}">
                            <h2 style="color: #1B5E20; margin: 0;">{mejor['Nombre_Vista']}</h2>
                            <h1 style="font-size: 3rem; margin: 10px 0; color: #000;">${int(mejor['Precio'])}</h1>
                            <p style="color: #444; font-weight: bold;">📍 A {mejor['Km']} km</p>
                        </div>
                    """, unsafe_allow_html=True)
                    wa = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                    st.markdown(f'<a href="https://wa.me/{wa}" target="_blank" class="btn-wa">💬 AGENDAR CITA</a>', unsafe_allow_html=True)

                with col_mapa: folium_static(m_folium, width=500, height=450)
                st.dataframe(final_res[['Nombre_Vista', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else: st.error("No se encontraron sedes.")
        except Exception as e: st.error(f"Error técnico: {e}")

# --- 6. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Clínicas")
    clave = st.text_input("Introduce tu clave", type="password")
    if clave in ACCESOS_CLINICAS:
        st.success(f"Bienvenido {ACCESOS_CLINICAS[clave]}")
