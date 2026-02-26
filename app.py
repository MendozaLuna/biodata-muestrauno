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
    
    /* TITULOS Y TEXTOS GENERALES */
    label, p, h1, h2, h3, span { color: #101828 !important; font-weight: 700 !important; }

    /* LOGO Y SLOGAN */
    .brand-title { color: #004D40 !important; font-size: 5rem !important; font-weight: 800 !important; letter-spacing: -2px; margin-bottom: 0px; text-align: center; }
    .brand-slogan { color: #26A69A !important; font-size: 1.5rem !important; font-weight: 400 !important; margin-top: -10px; margin-bottom: 40px; text-align: center; }
    
    /* BOTONES ESTILO PÍLDORA (TEXTO BLANCO) */
    div.stButton > button { 
        background: linear-gradient(135deg, #00796B 0%, #004D40 100%) !important; 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        width: 100%; 
        border-radius: 50px !important;
        border: none !important; 
        padding: 12px 24px !important;
        box-shadow: 0 4px 12px rgba(0, 121, 107, 0.2) !important;
    }
    
    /* CONTENEDOR DE IA (INFO BOX) CON LETRAS BLANCAS */
    .med-info-box { 
        background: linear-gradient(135deg, #00796B 0%, #26A69A 100%) !important; 
        padding: 20px; 
        border-radius: 20px; 
        margin: 15px 0; 
        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
    }
    .med-info-box h4, .med-info-box p, .med-info-box span { 
        color: #FFFFFF !important; 
        font-weight: 500 !important; 
    }

    /* TARJETAS DE RESULTADOS */
    .premium-card { border-radius: 25px; padding: 30px; background: #FFFDF0; box-shadow: 0 10px 25px rgba(212,175,55,0.15); text-align: center; border: 1px solid #D4AF37 !important; }
    .pro-card { border-radius: 25px; padding: 30px; background: #FFFFFF; box-shadow: 0 10px 25px rgba(0,121,107,0.1); text-align: center; border: 1px solid #00796B !important; }
    .standard-card { border-radius: 25px; padding: 30px; background: #FFFFFF; text-align: center; border: 1px solid #EAECF0 !important; }

    /* BOTONES DE ACCIÓN */
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 14px; text-align: center; border-radius: 50px; text-decoration: none; display: block; font-weight: 700; margin-top: 15px; }
    .btn-share { color: #00796B !important; text-align: center; text-decoration: underline; display: block; font-weight: 600; margin-top: 10px; }
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

# --- 5. LÓGICA DE NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    # AQUÍ APLICAMOS LOS NUEVOS COLORES AL LOGO Y SLOGAN
    st.markdown('<p class="brand-title">BioData</p>', unsafe_allow_html=True)
    st.markdown('<p class="brand-slogan">Busca. Compara. Resuelve.</p>', unsafe_allow_html=True)
    
    col_p, col_e = st.columns(2)
    with col_p:
        if st.button("👤 PACIENTE\n\nBusco estudios", use_container_width=True):
            st.session_state.perfil = 'persona'; st.rerun()
    with col_e:
        if st.button("🏥 CLÍNICA ALIADA\n\nPortal de gestión", use_container_width=True):
            st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 6. CONTENIDO PACIENTE ---
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
                    if p == "Pro": return "pro-card", "✅ SEDE PRO", "#1B5E20", 2
                    return "standard-card", "📍 SEDE BÁSICA", "#808080", 3

                res_df['Estilo_Datos'] = res_df.apply(definir_estilo, axis=1)
                res_df['Orden_Plan'] = res_df['Estilo_Datos'].apply(lambda x: x[3])
                final = res_df.sort_values(by=['Orden_Plan', 'Precio' if prio == "Precio" else 'Km'])
                mejor = final.iloc[0]
                card_class, badge_text, badge_color, _ = mejor['Estilo_Datos']
                
                col_i, col_m = st.columns([1, 1])
                with col_i:
                    st.markdown(f"""<div class="{card_class}"><p style="color: {badge_color}; font-weight: 900;">{badge_text}</p><h2>{mejor['Nombre']}</h2><h1>${int(mejor['Precio'])}</h1><p>📍 A {mejor['Km']} km</p></div>""", unsafe_allow_html=True)
                    wa_num = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                    texto_wa = f"Saludos. Consulté su sede a través de *BioData* para realizarme el estudio: {n_est}. Quisiera confirmar los horarios de atención y si requieren preparación previa. Muchas gracias."
                    st.markdown(f'<a href="https://wa.me/{wa_num}?text={urllib.parse.quote(texto_wa)}" target="_blank" class="btn-wa">📱 CONTACTAR</a>', unsafe_allow_html=True)
                    
                    t_share = f"*BioData*: {mejor['Nombre']} ofrece {n_est} por ${int(mejor['Precio'])}. 📍 Ubicación: {mejor.get('Direccion', 'N/A')}. 📱 Contacto: {wa_num}"
                    st.markdown(f'<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(t_share)}" target="_blank" class="btn-share">🔗 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)
                
                with col_m: folium_static(m_folium, width=500, height=400)
                st.write("---")
                st.write("### 🏥 Todas las sedes disponibles:")
                tabla_v = final[['Nombre', 'Precio', 'Km', 'Direccion', 'Plan']].copy()
                tabla_v.columns = ['Sede', 'Precio ($)', 'Distancia (Km)', 'Ubicación', 'Plan']
                st.dataframe(tabla_v, use_container_width=True, hide_index=True)
                
                st.markdown('<div class="suggestion-box">', unsafe_allow_html=True)
                st.subheader("¿No encuentras tu clínica?")
                cs1, cs2 = st.columns(2); sn_p = cs1.text_input("Nombre Clínica:", key="sn_p"); sz_p = cs2.text_input("Zona:", key="sz_p")
                if st.button("📩 ENVIAR SUGERENCIA", key="send_sug_p"): 
                    if sn_p and sz_p: enviar_sugerencia(sn_p, sz_p)
                st.markdown('</div>', unsafe_allow_html=True)
            else: st.error("No se encontraron sedes.")
        except Exception as e: st.error(f"Error: {e}")

# --- 7. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Gestión de Clínicas")
    clave = st.text_input("Clave de Acceso", type="password", key="pass_e")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        tab_stats, tab_premium, tab_oferta = st.tabs(["📊 Estadísticas Base", "💎 ANÁLISIS PREMIUM", "⚡ OFERTA RELÁMPAGO"])
        
        with tab_stats:
            c_f1, c_f2 = st.columns(2)
            with c_f1: f_ini = st.date_input("Desde:", date.today() - timedelta(days=7), key="stats_desde")
            with c_f2: f_fin = st.date_input("Hasta:", date.today(), key="stats_hasta")
            try:
                resp = supabase.table("busquedas_stats").select("*").execute()
                df_full = pd.DataFrame(resp.data)
                if not df_full.empty:
                    df_full['fecha_dt'] = pd.to_datetime(df_full['fecha'], errors='coerce').dt.tz_localize(None)
                    df_stats = df_full[(df_full['fecha_dt'] >= pd.Timestamp(f_ini)) & (df_full['fecha_dt'] <= pd.Timestamp(f_fin) + timedelta(days=1))].copy()
                    if not df_stats.empty:
                        st.metric("Búsquedas Totales", len(df_stats))
                        top_data = df_stats['estudio'].value_counts().head(5).reset_index()
                        top_data.columns = ['estudio', 'conteo']
                        chart = alt.Chart(top_data).mark_bar().encode(x=alt.X('estudio', sort='-y'), y='conteo', color='estudio').properties(height=300)
                        st.altair_chart(chart, use_container_width=True)
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df_stats.to_excel(writer, index=False)
                        st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="BioData_Reporte.xlsx")
            except Exception as e: st.error(f"Error: {e}")

        with tab_premium:
            if nombre_c == "ADMIN" or "Premium" in clave:
                st.subheader("📍 Mapa de Calor de Competencia (Market Intel)")
                col_mapa, col_intel = st.columns([1.5, 1])
                
                with col_mapa:
                    puntos_calor = df_stats[['lat', 'lon']].dropna().values.tolist() if not df_stats.empty else []
                    m_premium = folium.Map(location=[10.48, -66.90], zoom_start=12, tiles="cartodbpositron")
                    if puntos_calor: HeatMap(puntos_calor, radius=15, blur=20).add_to(m_premium)
                    df_clinicas = pd.read_excel("base_clinicas.xlsx")
                    geo = Nominatim(user_agent="premium_intel_v_final_safe")
                    for _, clinica in df_clinicas.iterrows():
                        try:
                            color_icono = 'gold' if 'Premium' in str(clinica.get('Plan','')) else 'blue'
                            loc = geo.geocode(clinica['Direccion'])
                            if loc: folium.Marker([loc.latitude, loc.longitude], popup=f"{clinica['Nombre']}", icon=folium.Icon(color=color_icono)).add_to(m_premium)
                        except: continue 
                    folium_static(m_premium, width=650, height=450)
                
                with col_intel:
                    st.markdown("""
                    <div style="background-color: #FFF9E6; padding: 20px; border-radius: 10px; border-left: 5px solid #D4AF37;">
                        <h4 style="color: #996515; margin-top: 0;">📍 Análisis de Ubicación</h4>
                        <p style="color: #333; font-size: 0.95rem;">El mapa de calor identifica concentraciones críticas de pacientes en zonas desatendidas.</p>
                    </div>
                    """, unsafe_allow_html=True)

                # --- CUADRO DE MARKET SHARE (REINSTALADO) ---
                st.markdown("---")
                st.subheader("📊 Cuadro de Market Share")
                market_data = {
                    "Indicador": ["Precio Promedio OCT", "Tiempo de Respuesta", "Clics por cada 100 búsquedas"],
                    "Tu Clínica": ["$85", "< 5 min", "12"],
                    "Promedio Competencia": ["$70", "15 min", "25"],
                    "Diferencia": ["🔴 +21%", "🟢 -66%", "🔴 -52%"]
                }
                st.table(pd.DataFrame(market_data))
                st.markdown("""<div style="background-color: #F0F4F8; padding: 20px; border-radius: 10px; border-left: 5px solid #1B5E20;"><h4 style="color: #1B5E20; margin-top: 0;">🧠 Recomendación Estratégica</h4><p>Basado en los datos, su clínica tiene fortaleza en respuesta pero debilidad en precio. Acción: Reducir OCT a <b>$75</b>.</p></div>""", unsafe_allow_html=True)
            else:
                st.error("🔒 Exclusivo Plan PREMIUM.")

        with tab_oferta:
            st.subheader("⚡ Crear Oferta Relámpago (IA)")
            if nombre_c == "ADMIN" or "Pro" in clave or "Premium" in clave:
                c1, c2 = st.columns(2)
                lista_estudios = ["OCT de Mácula", "Campimetría", "Topografía", "Retinografía", "Paquimetría", "Otro (Escribir manualmente...)"]
                sel_of = c1.selectbox("Seleccione Estudio:", lista_estudios)
                estudio_final = sel_of
                if sel_of == "Otro (Escribir manualmente...)": estudio_final = st.text_input("Escriba el nombre del examen:")
                pre_of = c2.number_input("Precio de Oferta ($):", min_value=1, value=50)
                if st.button("🪄 GENERAR PUBLICIDAD CON IA"):
                    if estudio_final:
                        with st.spinner("Redactando..."):
                            copy = generar_copy_oferta(estudio_final, pre_of)
                            st.text_area("Copy para Redes:", copy, height=250)
            else: st.warning("🔒 Requiere Plan PRO o PREMIUM.")
