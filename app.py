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

# --- 5. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"):
        st.session_state.perfil = None; st.rerun()

    st.title("🔍 Buscador de Estudios")

    # --- SECCIÓN DE UBICACIÓN ---
    st.markdown("### 📍 ¿Dónde te encuentras?")
    
    col_btn, col_txt = st.columns([1, 2])
    
    u_lat, u_lon = None, None
    
    with col_btn:
        # El componente JS se ejecuta siempre, si hay permiso captura la data
        loc = streamlit_js_eval(data_string="navigator.geolocation", want_output=True, key="get_pos")
        if loc and 'coords' in loc:
            u_lat = loc['coords']['latitude']
            u_lon = loc['coords']['longitude']
            st.success("✅ GPS Activo")
    
    with col_txt:
        # Si el GPS falla, usamos lo que el usuario escriba aquí
        u_city = st.text_input("Ciudad (si el GPS no carga):", "Caracas, Venezuela")

    st.write("---")

    # Columnas de búsqueda
    c_op1, c_op2 = st.columns(2)
    with c_op1: 
        prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True)
    with c_op2: 
        manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")

    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"])

    if st.button("🚀 BUSCAR MEJORES OPCIONES"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            with st.spinner('Procesando...'):
                model = genai.GenerativeModel('models/gemini-flash-latest')
                if manual:
                    res = model.generate_content(f"Define brevemente: {manual}. Máximo 20 palabras.")
                    nombre_estudio, desc_estudio = manual.upper(), res.text.strip()
                elif up_img:
                    img = PIL.Image.open(up_img)
                    res = model.generate_content(["Extrae: NOMBRE | DESCRIPCIÓN (20 palabras).", img])
                    partes = res.text.split('|')
                    nombre_estudio = partes[0].strip().upper()
                    desc_estudio = partes[1].strip() if len(partes) > 1 else "Estudio ocular."
                else:
                    st.warning("Escribe el examen."); st.stop()

            st.markdown(f'''<div class="med-info-box"><h4>📋 {nombre_estudio}</h4><p>{desc_estudio}</p></div>''', unsafe_allow_html=True)

            # Lógica de distancias
            geo = Nominatim(user_agent="biodata_v26")
            if u_lat and u_lon:
                t_lat, t_lon = u_lat, u_lon
            else:
                l_m = geo.geocode(u_city)
                t_lat, t_lon = (l_m.latitude, l_m.longitude) if l_m else (10.48, -66.90)

            def dist(la1, lo1, la2, lo2):
                R = 6371.0
                dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
                return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)

            # Filtrar por nombre
            res_df = df[df['Estudio'].astype(str).str.contains(manual.lower() if manual else "", case=False)].copy()
            
            if not res_df.empty:
                kms = []
                m = folium.Map(location=[t_lat, t_lon], zoom_start=12)
                for _, row in res_df.iterrows():
                    d = 99.0
                    l = geo.geocode(str(row.get('Direccion','')))
                    if l: 
                        d = dist(t_lat, t_lon, l.latitude, l.longitude)
                        folium.Marker([l.latitude, l.longitude], tooltip=row['Nombre']).add_to(m)
                    kms.append(d)
                
                res_df['Km'] = kms
                res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                final = res_df.sort_values(by='Precio' if prio == "Precio" else 'Km')
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    mejor = final.iloc[0]
                    st.success(f"### 🏆 Mejor Opción: {mejor['Nombre']}")
                    st.metric("Precio", f"${int(mejor['Precio'])}")
                    st.metric("Distancia", f"{mejor['Km']} km")
                with c2:
                    folium_static(m, width=400, height=300)
                
                st.dataframe(final[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else:
                st.error("No se encontraron resultados.")
        except Exception as e:
            st.error(f"Error: {e}")

# --- 6. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Clínicas")
    clave = st.text_input("Clave", type="password")
    if clave in ACCESOS_CLINICAS:
        st.success(f"Bienvenido {ACCESOS_CLINICAS[clave]}")
