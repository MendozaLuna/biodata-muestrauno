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

# --- FUNCIONES CON CACHE PARA AHORRAR API ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

@st.cache_data(show_spinner=False)
def analizar_imagen_ai(img_bytes):
    # Nota: Pasamos bytes porque PIL.Image no es fácilmente serializable para cache
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

    def registrar_clic_real(clinica, estudio):
        try:
            data = {"clinica": clinica, "estudio": estudio, "fecha": datetime.now().isoformat()}
            supabase.table("clics").insert(data).execute()
        except: pass 

    def calcular_distancia(lat1, lon1, lat2, lon2):
        try:
            R = 6371.0 
            dlat = math.radians(float(lat2) - float(lat1))
            dlon = math.radians(float(lon2) - float(lon1))
            a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return round(R * c, 1)
        except: return 99.0

    def limpiar_texto(t):
        if not isinstance(t, str): return ""
        return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

    st.title("🔍 Buscador de Estudios")
    u_city = st.text_input("📍 Tu ubicación actual:", "Caracas, Venezuela")
    
    c_op1, c_op2 = st.columns(2)
    with c_op1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True)
    with c_op2: manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")

    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"])

    if st.button("🚀 BUSCAR MEJORES OPCIONES"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            with st.spinner('Procesando solicitud...'):
                try:
                    if manual:
                        nombre_estudio, desc_estudio = analizar_texto_ai(manual)
                    elif up_img:
                        # Convertimos a bytes para el cache
                        img_bytes = up_img.getvalue()
                        nombre_estudio, desc_estudio = analizar_imagen_ai(img_bytes)
                    else:
                        st.warning("Por favor escribe el examen o sube una orden."); st.stop()
                except Exception as e:
                    if "429" in str(e):
                        st.warning("⚠️ Límite excedido. Reintentando en modo básico...")
                        nombre_estudio = manual.upper() if manual else "ESTUDIO"
                        desc_estudio = "Buscando en base de datos..."
                    else: raise e

            st.markdown(f'''<div class="med-info-box"><h4>📋 {nombre_estudio}</h4><p>{desc_estudio}</p></div>''', unsafe_allow_html=True)

            palabras_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in limpiar_texto(x) for k in palabras_clave))].copy()

            if not res_df.empty:
                geo = Nominatim(user_agent="biodata_geo_final_v26")
                u_loc = geo.geocode(u_city)
                u_lat, u_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                
                kms = []
                m_folium = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                for _, row in res_df.iterrows():
                    d = 99.0
                    try:
                        l = geo.geocode(str(row.get('Direccion','')))
                        if l: 
                            d = calcular_distancia(u_lat, u_lon, l.latitude, l.longitude)
                            folium.Marker([l.latitude, l.longitude], tooltip=row['Nombre']).add_to(m_folium)
                    except: pass
                    kms.append(d)
                
                res_df['Km'] = kms
                res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                res_df['Es_Premium'] = res_df['Plan'].astype(str).str.contains('Premium', case=False, na=False)
                res_df['Nombre_Vista'] = res_df.apply(lambda x: f"⭐ {x['Nombre']}" if x['Es_Premium'] else x['Nombre'], axis=1)
                
                final_res = res_df.sort_values(by='Precio' if prio == "Precio" else 'Km')
                mejor = final_res.iloc[0]
                registrar_clic_real(mejor['Nombre'], nombre_estudio)

                col_info, col_mapa = st.columns([1, 1])
                with col_info:
                    es_p = mejor['Es_Premium']
                    badge_html = '<div class="premium-badge">✨ OPCIÓN PREMIUM</div>' if es_p else ""
                    st.markdown(f"""
                        <div class="{'premium-card' if es_p else 'standard-card'}">
                            {badge_html}
                            <h2 style="color: #1B5E20; margin: 0;">{mejor['Nombre_Vista']}</h2>
                            <h1 style="font-size: 3rem; margin: 10px 0; color: #000;">${int(mejor['Precio'])}</h1>
                            <p style="color: #444; font-weight: bold;">📍 A {mejor['Km']} km de distancia</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    wa_num = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                    st.markdown(f'<a href="https://wa.me/{wa_num}?text=Cita%20BioData:%20{nombre_estudio}" target="_blank" class="btn-wa">💬 AGENDAR CITA</a>', unsafe_allow_html=True)
                    st.markdown(f'<a href="https://api.whatsapp.com/send?text=BioData:%20{mejor["Nombre"]}" target="_blank" class="btn-share">📢 COMPARTIR OPCIÓN</a>', unsafe_allow_html=True)

                with col_mapa: folium_static(m_folium, width=500, height=450)

                st.write("---")
                st.write("### 🏥 Todas las sedes disponibles:")
                tabla_vista = final_res[['Nombre_Vista', 'Precio', 'Km', 'Direccion']].copy()
                tabla_vista.columns = ['Nombre', 'Precio ($)', 'Distancia (Km)', 'Ubicación']
                st.dataframe(tabla_vista, use_container_width=True, hide_index=True)
            else: st.error("No se encontraron sedes.")
        except Exception as e: st.error(f"Error técnico: {e}")

# --- 6. CONTENIDO EMPRESA (Simplificado) ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Clínicas")
    clave = st.text_input("Introduce tu clave", type="password")
    if clave in ACCESOS_CLINICAS:
        st.success(f"Bienvenido {ACCESOS_CLINICAS[clave]}")
        # Aquí va la lógica de métricas que ya teníamos...
