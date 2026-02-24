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

# --- A. PERFIL PERSONA (PACIENTE) ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver al Inicio", key="v_p"):
        st.session_state.perfil = None
        st.rerun()

    def registrar_clic_real(clinica, estudio):
        try:
            data = {"clinica": clinica, "estudio": estudio, "fecha": datetime.now().isoformat()}
            supabase.table("clics").insert(data).execute()
        except: pass 

    def calcular_distancia(lat1, lon1, lat2, lon2):
        try:
            R = 6371.0 
            dlat, dlon = math.radians(float(lat2)-float(lat1)), math.radians(float(lon2)-float(lon1))
            a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
            return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)
        except: return 99.0

    def limpiar_texto(t):
        if not isinstance(t, str): return ""
        return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

    st.title("🔍 BioData - Buscador")
    u_city = st.text_input("📍 Tu ubicación actual:", "Caracas, Venezuela")

    c_op1, c_op2 = st.columns(2)
    with c_op1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True)
    with c_op2: manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")

    up_img = st.file_uploader("O sube foto de la orden", type=["jpg", "jpeg", "png"])

    if st.button("🚀 BUSCAR MEJORES OPCIONES"):
        if not up_img and not manual:
            st.warning("⚠️ Ingresa un estudio.")
        else:
            try:
                df = pd.read_excel("base_clinicas.xlsx")
                df.columns = [str(c).strip().capitalize() for c in df.columns]
                
                model = genai.GenerativeModel('models/gemini-flash-latest')
                with st.spinner('Analizando examen...'):
                    if manual:
                        res = model.generate_content(f"Para qué sirve el examen oftalmológico: {manual} en 20 palabras.")
                        nombre_estudio, descripcion_estudio = manual.upper(), res.text.strip()
                    else:
                        res = model.generate_content(["NOMBRE DEL EXAMEN | DESCRIPCIÓN (20 palabras)", PIL.Image.open(up_img)])
                        partes = res.text.split('|')
                        nombre_estudio = partes[0].strip().upper()
                        descripcion_estudio = partes[1].strip() if len(partes) > 1 else ""

                st.markdown(f'''<div class="med-info-box"><p class="label">📋 Examen Detectado</p><h4>{nombre_estudio}</h4><p class="desc">{descripcion_estudio}</p></div>''', unsafe_allow_html=True)

                # --- LÓGICA DE BÚSQUEDA FLEXIBLE MEJORADA ---
                palabras_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
                res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in limpiar_texto(x) for k in palabras_clave))].copy()

                if not res_df.empty:
                    geo = Nominatim(user_agent="biodata_fix_v1")
                    u_loc = geo.geocode(u_city)
                    u_lat, u_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    kms = []
                    for _, row in res_df.iterrows():
                        d = 99.0
                        try:
                            l = geo.geocode(str(row.get('Direccion','')))
                            if l: d = calcular_distancia(u_lat, u_lon, l.latitude, l.longitude)
                        except: pass
                        kms.append(d)
                    
                    res_df['Km'] = kms
                    res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                    
                    p_df = res_df[res_df['Plan'].str.capitalize() == 'Premium'].sort_values(by='Precio' if prio == "Precio" else 'Km')
                    b_df = res_df[res_df['Plan'].str.capitalize() != 'Premium'].sort_values(by='Precio' if prio == "Precio" else 'Km')
                    final_res = pd.concat([p_df, b_df])
                    
                    mejor = final_res.iloc[0]
                    registrar_clic_real(mejor['Nombre'], nombre_estudio)

                    st.markdown(f'<div class="premium-card"><h2>{mejor["Nombre"]}</h2><h1 style="color:#1B5E20">${int(mejor["Precio"])}</h1><p>📍 A {mejor["Km"]} km de ti</p></div>', unsafe_allow_html=True)
                    
                    if 'Whatsapp' in mejor and not pd.isna(mejor['Whatsapp']):
                        url_wa = f"https://wa.me/{str(mejor['Whatsapp']).split('.')[0]}?text=Cita%20BioData:%20{nombre_estudio}"
                        st.markdown(f'<a href="{url_wa}" target="_blank" class="btn-wa">💬 AGENDAR CITA</a>', unsafe_allow_html=True)

                    st.write("### 🏥 Todas las opciones:")
                    df_final = final_res[['Nombre', 'Precio', 'Km', 'Direccion', 'Plan']].copy()
                    df_final['Nombre'] = df_final.apply(lambda x: f"⭐ {x['Nombre']}" if str(x['Plan']).capitalize() == 'Premium' else x['Nombre'], axis=1)
                    st.dataframe(df_final[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
                else: 
                    st.error("No se encontraron sedes que coincidan con este estudio. Intenta escribiendo una sola palabra (ej: OCT).")
            except Exception as e: st.error(f"Error: {e}")

# --- B. PERFIL CLÍNICA (PORTAL ALIADO) ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver al Inicio", key="v_e"):
        st.session_state.perfil = None
        st.rerun()

    st.title("🏥 Portal de Clínicas")
    clave = st.text_input("Introduce tu clave de Aliado", type="password")
    
    if clave in ACCESOS_CLINICAS:
        nombre_clinica = ACCESOS_CLINICAS[clave]
        try:
            res_db = supabase.table("clics").select("*").execute()
            df_clics = pd.DataFrame(res_db.data)

            if not df_clics.empty:
                if nombre_clinica == "ADMIN":
                    st.success("👋 Modo Administrador")
                    stats_vista = df_clics
                else:
                    st.success(f"👋 ¡Hola **{nombre_clinica}**!")
                    stats_vista = df_clics[df_clics['clinica'] == nombre_clinica]

                c1, c2 = st.columns(2)
                with c1: st.metric("Pacientes Derivados", len(stats_vista))
                with c2: 
                    if not stats_vista.empty:
                        st.metric("Servicio Líder", stats_vista['estudio'].value_counts().idxmax())

                if not stats_vista.empty:
                    st.subheader("📊 Rendimiento")
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        stats_vista['fecha_dt'] = pd.to_datetime(stats_vista['fecha']).dt.date
                        st.line_chart(stats_vista['fecha_dt'].value_counts().sort_index())
                    with col_g2:
                        st.bar_chart(stats_vista['estudio'].value_counts())

                    st.subheader("📝 Detalle de Consultas")
                    df_detalle = stats_vista[['fecha', 'estudio']].copy()
                    df_detalle['fecha'] = pd.to_datetime(df_detalle['fecha']).dt.strftime('%d/%m/%Y %H:%M')
                    df_detalle.columns = ['Fecha', 'Examen Solicitado']
                    st.dataframe(df_detalle.sort_values(by='Fecha', ascending=False), use_container_width=True, hide_index=True)

                    csv = df_detalle.to_csv(index=False).encode('utf-8')
                    st.download_button("📊 Descargar Reporte (CSV)", csv, f'reporte_{nombre_clinica}.csv', 'text/csv')
            else: st.info("No hay datos aún.")
        except Exception as e: st.error(f"Error: {e}")
