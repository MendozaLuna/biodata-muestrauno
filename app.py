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
from streamlit_js_eval import get_geolocation

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
    "PampatarPremium26": "Salud Visual Margarita",
    "OftalmoPlus26": "Oftalmo Plus"
}

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

loc = get_geolocation()

if "u_lat" not in st.session_state:
    if loc:
        st.session_state.u_lat = loc['coords']['latitude']
        st.session_state.u_lon = loc['coords']['longitude']
    else:
        st.session_state.u_lat = 10.4806
        st.session_state.u_lon = -66.9036
        
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }
    .brand-title { color: #004D40 !important; font-size: 5rem !important; font-weight: 800 !important; text-align: center !important; }
    .brand-slogan { color: #000000 !important; font-size: 1.5rem !important; text-align: center !important; margin-bottom: 40px !important; }
    div.stButton > button { background: linear-gradient(135deg, #26A69A 0%, #00796B 100%) !important; color: white !important; border-radius: 50px !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCIONES ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

@st.cache_data(show_spinner=False)
def generar_copy_oferta(estudio, precio):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    prompt = f"Escribe un copy publicitario para una clínica. Oferta: {estudio} por ${precio}. Corto con emojis."
    res = model.generate_content(prompt)
    return res.text

@st.cache_data(show_spinner=False)
def analizar_imagen_ai(img_bytes):
    img = PIL.Image.open(io.BytesIO(img_bytes))
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(["NOMBRE | DESCRIPCIÓN (20 palabras).", img])
    partes = res.text.split('|')
    nombre = partes[0].strip().upper()
    desc = partes[1].strip() if len(partes) > 1 else "Estudio médico."
    return nombre, desc

def registrar_busqueda(lat, lon, estudio):
    try: supabase.table("busquedas_stats").insert({"lat": float(lat), "lon": float(lon), "estudio": str(estudio), "fecha": datetime.now().isoformat()}).execute()
    except: pass

def calcular_distancia(la1, lo1, la2, lo2):
    R = 6371.0
    dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)

# --- 5. NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown('<h1 class="brand-title">BioData</h1>', unsafe_allow_html=True)
    st.markdown('<p class="brand-slogan">Conecta. Explora. Soluciona.</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👤 PACIENTE\n\nBusco estudios", use_container_width=True): st.session_state.perfil = 'persona'; st.rerun()
    with c2:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión", use_container_width=True): st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 6. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if 'busqueda_realizada' not in st.session_state:
        st.session_state.busqueda_realizada = False
        st.session_state.final_df = None

    if st.button("⬅️ Volver", key="back_p"): 
        st.session_state.perfil = None
        st.session_state.busqueda_realizada = False
        st.rerun()

    st.title("🔍 Buscador de Estudios")
    u_city = st.text_input("Tu ubicación:", value="Caracas", key="city_p")
    
    col1, col2 = st.columns(2)
    with col1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True, key="prio_p")
    with col2: manual = st.text_input("⌨️ ¿Qué examen buscas?", key="ex_p")
    
    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "png"], key="img_p")

    if st.button("🚀 BUSCAR MEJORES OPCIONES", key="btn_p"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            with st.spinner('Buscando...'):
                if manual: n_est, d_est = analizar_texto_ai(manual)
                elif up_img: n_est, d_est = analizar_imagen_ai(up_img.getvalue())
                else: st.warning("Escribe un examen."); st.stop()

                st.session_state.n_est_guardado = n_est
                geo = Nominatim(user_agent="biodata_app")
                loc_m = geo.geocode(f"{u_city}, Venezuela")
                c_lat, c_lon = (loc_m.latitude, loc_m.longitude) if loc_m else (10.48, -66.90)
                st.session_state.u_lat, st.session_state.u_lon = c_lat, c_lon
                registrar_busqueda(c_lat, c_lon, n_est)

                def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
                palabras = [p for p in norm(n_est).split() if len(p) > 2]
                res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()

                if not res_df.empty:
                    res_df['Km'] = res_df.apply(lambda r: calcular_distancia(c_lat, c_lon, float(r['Latitud']), float(r['Longitud'])), axis=1)
                    mapeo_p = {"Premium": 0, "Pro": 1, "Básico": 2}
                    res_df['Prioridad_Plan'] = res_df['Plan'].str.strip().str.capitalize().map(mapeo_p).fillna(2)
                    c_ord = 'Precio' if prio == "Precio" else 'Km'
                    st.session_state.final_df = res_df.sort_values(by=['Prioridad_Plan', c_ord], ascending=[True, True])
                    st.session_state.busqueda_realizada = True
                    st.rerun()
        except Exception as e: st.error(f"Error: {e}")

    # MOSTRAR RESULTADOS
    if st.session_state.get('busqueda_realizada') and st.session_state.final_df is not None:
        df_res = st.session_state.final_df
        st.markdown("### 🏥 Sedes Recomendadas")
        
        # Tabla Interactiva
        p_min = df_res['Precio'].min()
        def estilo(row): return ['background-color: #d4edda; font-weight: bold'] * len(row) if row['Precio'] == p_min else [''] * len(row)
        
        seleccion = st.dataframe(
            df_res[['Nombre', 'Precio', 'Km', 'Plan']].style.apply(estilo, axis=1),
            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="tabla_p"
        )

        idx = seleccion.selection.rows[0] if seleccion.selection.rows else 0
        mostrar = df_res.iloc[idx]

        # Tarjeta Dinámica
        plan = str(mostrar.get('Plan', 'Básico')).strip().capitalize()
        bg, brd = ("#FFFDF0", "#D4AF37") if plan == "Premium" else ("#F5F5F5", "#C0C0C0") if plan == "Pro" else ("#E3F2FD", "#2196F3")
        
        st.markdown(f"""
            <div style="background-color: {bg}; padding: 20px; border-radius: 15px; border: 2px solid {brd}; text-align: center; margin-top: 20px;">
                <h2 style="margin:0;">{mostrar['Nombre']}</h2>
                <h1 style="margin:5px 0;">${int(mostrar['Precio'])}</h1>
                <p style="color: #666;">📍 A {mostrar['Km']} km de distancia</p>
            </div>
        """, unsafe_allow_html=True)

        # Botones de Acción
        wa_num = str(mostrar.get('Whatsapp', '584120000000')).split('.')[0]
        est_n = st.session_state.get('n_est_guardado', 'estudio')
        msg = urllib.parse.quote(f"Hola, consulto por {est_n} en {mostrar['Nombre']} via BioData.")
        
        c_a, c_b = st.columns(2)
        with c_a: st.link_button("💬 Contactar WhatsApp", f"https://wa.me/{wa_num}?text={msg}", use_container_width=True)
        with c_b: 
            url_m = f"https://www.google.com/maps/dir/?api=1&destination={mostrar['Latitud']},{mostrar['Longitud']}"
            st.link_button("🗺️ Ver en Mapa", url_m, use_container_width=True)

# --- 7. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Gestión")
    clave = st.text_input("Clave de Acceso", type="password")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        
        tab1, tab2, tab3 = st.tabs(["📊 Estadísticas", "💎 Análisis", "🛠️ Inventario"])
        
        with tab1:
            st.subheader("Búsquedas Recientes")
            try:
                resp = supabase.table("busquedas_stats").select("*").execute()
                df_s = pd.DataFrame(resp.data)
                if not df_s.empty:
                    st.metric("Total Búsquedas", len(df_s))
                    top = df_s['estudio'].value_counts().head(5).reset_index()
                    st.altair_chart(alt.Chart(top).mark_bar().encode(x='estudio', y='count'), use_container_width=True)
            except: st.info("Cargando datos...")

        with tab2:
            if "Premium" in clave or clave == "AdminBio2026":
                st.write("Análisis de Mercado Activo")
                # Aquí puedes integrar el mapa de calor que me pasaste
            else: st.warning("Requiere Plan Premium.")

        with tab3:
            st.write("Estado de Equipos")
            eq = st.selectbox("Equipo:", ["OCT", "Láser", "Campímetro"])
            est = st.radio("Estado:", ["Operativo", "Mantenimiento"])
            if st.button("Actualizar"): st.success("Guardado.")

# --- 8. PIE DE PÁGINA ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: 12px;'>BioData 2026</p>", unsafe_allow_html=True)

# --- 8. PIE DE PÁGINA ---
st.markdown("---")
with st.form("buzon_final", clear_on_submit=True):
    st.subheader("📩 Buzón de Sugerencias")
    nombre_b = st.text_input("Nombre (Opcional)")
    asunto_b = st.selectbox("Asunto:", ["Nueva Sede", "Mejora App", "Reportar Error", "Otro"])
    mensaje_b = st.text_area("Tu comentario:")
    if st.form_submit_button("Enviar a BioData"):
        if mensaje_b: 
            st.success("✅ Recibido.")
        else: 
            st.warning("Escribe un mensaje.")

st.markdown("<p style='text-align: center; color: grey; font-size: 12px;'>BioData 2026 - Conecta. Explora. Soluciona.</p>", unsafe_allow_html=True)
