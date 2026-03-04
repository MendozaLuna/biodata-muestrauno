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
    
    .brand-title { 
        color: #004D40 !important; 
        font-size: 5rem !important; 
        font-weight: 800 !important; 
        letter-spacing: -2px !important; 
        margin-bottom: 0px !important; 
        text-align: center !important; 
    }
    .brand-slogan { 
        color: #26A69A !important; 
        font-size: 1.5rem !important; 
        font-weight: 400 !important; 
        margin-top: -10px !important; 
        margin-bottom: 40px !important; 
        text-align: center !important; 
    }
    
    div.stButton > button { 
        background: linear-gradient(135deg, #26A69A 0%, #00796B 100%) !important; 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        width: 100%; 
        border-radius: 50px !important;
        border: none !important; 
        padding: 12px 24px !important;
        box-shadow: 0 4px 15px rgba(38, 166, 154, 0.3) !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        white-space: pre-line;
    }

    div.stButton > button p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    div.stButton > button:hover {
        background: linear-gradient(135deg, #00897B 0%, #00695C 100%) !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(0, 121, 107, 0.4) !important;
    }
    
    .med-info-box { 
        background: linear-gradient(135deg, #00796B 0%, #26A69A 100%) !important; 
        padding: 25px; 
        border-radius: 20px; 
        margin: 20px 0; 
    }
    .med-info-box h4, .med-info-box p { color: #FFFFFF !important; }

    .premium-card, .pro-card, .standard-card { border-radius: 25px; padding: 30px; text-align: center; }
    .premium-card { background: #FFFDF0; border: 1px solid #D4AF37 !important; }
    .premium-card h1, .premium-card h2, .premium-card p { color: #101828 !important; }

    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 14px; text-align: center; border-radius: 50px; text-decoration: none; display: block; font-weight: 700; margin-top: 15px; }
    .btn-share { background-color: transparent !important; color: #00796B !important; text-align: center; text-decoration: none !important; display: block; font-weight: 600; margin-top: 10px; padding: 10px; border: 2px solid #00796B !important; border-radius: 50px; }
    
    .status-badge {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 10px;
    }
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
    st.markdown('<p class="brand-slogan">Busca. Compara. Soluciona.</p>', unsafe_allow_html=True)
    
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
    if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
    st.session_state.final_df = None
    st.session_state.n_est_guardado = ""
    st.session_state.m_folium_guardado = None
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

    st.write("---")
    c1, c2 = st.columns(2)
    with c1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True, key="sort_radio")
    with c2: manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT...", key="exam_input")
    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"], key="img_uploader")

    if st.button("🚀 BUSCAR MEJORES OPCIONES", key="main_search"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]

            try:
                inv_resp = supabase.table("inventario_equipos").select("clinica, equipo, estado").order("ultima_actualizacion", desc=True).execute()
                df_inv_global = pd.DataFrame(inv_resp.data).drop_duplicates(subset=['clinica', 'equipo'])
            except:
                df_inv_global = pd.DataFrame(columns=['clinica', 'equipo', 'estado'])

            with st.spinner('Verificando disponibilidad técnica...'):
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
                def esta_operativo(clinica_nom, est_nom):
                    if df_inv_global.empty: return True
                    match = df_inv_global[(df_inv_global['clinica'] == clinica_nom) & 
                                         (df_inv_global['equipo'].apply(lambda x: x.lower() in est_nom.lower()))]
                    return match.iloc[0]['estado'] == "Operativo" if not match.empty else True
                
                res_df['Disponible'] = res_df.apply(lambda r: esta_operativo(r['Nombre'], n_est), axis=1)
                res_df = res_df[res_df['Disponible'] == True].copy()

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
                
                # --- LÓGICA DE SELECCIÓN DINÁMICA CORREGIDA ---
                if 'final_df' not in st.session_state or up_img or manual:
                    st.session_state.final_df = final
                    st.session_state.n_est_guardado = n_est
                    
                col_i, col_m = st.columns([1, 1])
                
                with col_i:
                    st.write("### 🏥 Sedes Disponibles")
                    st.caption("Haz clic en una fila para actualizar la tarjeta de contacto:")
                    
                    # Tabla Interactiva con el parámetro corregido
                    seleccion = st.dataframe(
                        final[['Nombre', 'Precio', 'Km']], 
                        use_container_width=True, 
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row"  # <--- Cambio clave aquí
                    )

                    # Determinar qué clínica mostrar
                    # En 'single-row', el resultado viene en rows
                    if seleccion.selection.rows:
                        idx_sel = seleccion.selection.rows[0]
                        mostrar = final.iloc[idx_sel]
                    else:
                        mostrar = mejor

                    # --- TARJETA DINÁMICA ---
                    card_class, badge_text, badge_color, _ = definir_estilo(mostrar)
                    
                    st.markdown(f"""
                        <div class="{card_class}">
                            <div class="status-badge">✔ EQUIPO DISPONIBLE HOY</div>
                            <p style="color: {badge_color}; font-weight: 900; margin-bottom: 5px;">{badge_text}</p>
                            <h2 style="margin: 0; color: #101828 !important;">{mostrar['Nombre']}</h2>
                            <h1 style="margin: 10px 0; color: #101828 !important;">${int(mostrar['Precio'])}</h1>
                            <p style="color: #667085 !important; margin: 0;">📍 A {mostrar['Km']} km</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    wa_num = str(mostrar.get('Whatsapp', '584120000000')).split('.')[0]
                    texto_wa = f"Saludos. Consulté su sede a través de *BioData* para el estudio: {n_est}. Quisiera confirmar disponibilidad."
                    
                    st.markdown(f'''
                        <div style="display: flex; flex-direction: column; gap: 5px; margin-top: 15px;">
                            <a href="https://wa.me/{wa_num}?text={urllib.parse.quote(texto_wa)}" target="_blank" class="btn-wa">
                                📱 CONTACTAR A {mostrar['Nombre'].upper()}
                            </a>
                        </div>
                    ''', unsafe_allow_html=True)
                
                with col_m: 
                    folium_static(m_folium, width=500, height=550)
            else: 
                st.error("No se encontraron sedes operativas para este estudio.")
        except Exception as e: 
            st.error(f"Error en la interacción: {e}")
            
# --- 7. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Gestión")
    clave = st.text_input("Clave de Acceso", type="password", key="pass_e")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        
        tab_stats, tab_premium, tab_oferta, tab_inventario = st.tabs([
            "📊 Estadísticas", "💎 ANÁLISIS PREMIUM", "⚡ OFERTA RELÁMPAGO", "🛠️ GESTIÓN DE INVENTARIO"
        ])
        
        with tab_stats:
            c_f1, c_f2 = st.columns(2)
            f_ini = c_f1.date_input("Desde:", date.today() - timedelta(days=7))
            f_fin = c_f2.date_input("Hasta:", date.today())
            try:
                resp = supabase.table("busquedas_stats").select("*").execute()
                df_full = pd.DataFrame(resp.data)
                if not df_full.empty:
                    df_full['fecha_dt'] = pd.to_datetime(df_full['fecha']).dt.tz_localize(None)
                    df_stats = df_full[(df_full['fecha_dt'] >= pd.Timestamp(f_ini)) & (df_full['fecha_dt'] <= pd.Timestamp(f_fin) + timedelta(days=1))].copy()
                    if not df_stats.empty:
                        st.metric("Búsquedas Totales", len(df_stats))
                        top_data = df_stats['estudio'].value_counts().head(5).reset_index()
                        top_data.columns = ['estudio', 'conteo']
                        st.altair_chart(alt.Chart(top_data).mark_bar().encode(x=alt.X('estudio', sort='-y'), y='conteo', color='estudio'), use_container_width=True)
            except: pass

        with tab_premium:
            if nombre_c == "ADMIN" or "Premium" in clave:
                st.subheader("📊 Cuadro de Market Share")
                m_data = {"Indicador": ["Precio OCT", "T. Respuesta", "Clicks/100"], "Tu Clínica": ["$85", "< 5 min", "12"], "Competencia": ["$70", "15 min", "25"], "Dif.": ["🔴 +21%", "🟢 -66%", "🔴 -52%"]}
                st.table(pd.DataFrame(m_data))
                
                st.markdown("---")
                st.subheader("📍 Mapa de Calor de Demanda")
                try:
                    resp = supabase.table("busquedas_stats").select("lat, lon").execute()
                    pts = pd.DataFrame(resp.data).dropna().values.tolist()
                    m_p = folium.Map(location=[10.48, -66.90], zoom_start=11)
                    if pts: HeatMap(pts).add_to(m_p)
                    folium_static(m_p)
                except: st.info("Cargando mapa...")
            else: st.error("🔒 Exclusivo Plan PREMIUM.")

        with tab_oferta:
            st.subheader("⚡ Crear Oferta Relámpago")
            if nombre_c == "ADMIN" or "Pro" in clave or "Premium" in clave:
                c1, c2 = st.columns(2)
                opciones = ["OCT de Mácula", "Campimetría", "Topografía", "Otro..."]
                sel_temp = c1.selectbox("Estudio:", opciones, key="sel_estudio_oferta")
                estudio_final = c1.text_input("Escriba el nombre:") if sel_temp == "Otro..." else sel_temp
                precio_of = c2.number_input("Precio ($):", min_value=1, value=50)
                
                if st.button("🪄 GENERAR CON IA"):
                    with st.spinner("Generando copy..."):
                        st.info(generar_copy_oferta(estudio_final, precio_of))
            else: st.warning("🔒 Requiere Plan PRO o PREMIUM.")

        with tab_inventario:
            st.subheader(f"🛠️ Gestión de Inventario - {nombre_c}")
            lista_equipos = ["OCT", "Retinógrafo", "Campímetro", "Ecógrafo Ocular", "Láser YAG", "Topógrafo"]
            
            with st.expander("Actualizar Estado de Equipo"):
                ce1, ce2 = st.columns(2)
                eq_sel = ce1.selectbox("Equipo:", lista_equipos, key="eq_inv")
                est_sel = ce2.radio("Estatus:", ["Operativo", "En Mantenimiento"], horizontal=True, key="st_inv")
                if st.button("Guardar Cambios", use_container_width=True):
                    try:
                        supabase.table("inventario_equipos").insert({
                            "clinica": nombre_c, "equipo": eq_sel, "estado": est_sel, "ultima_actualizacion": datetime.now().isoformat()
                        }).execute()
                        st.success("✅ Actualizado."); time.sleep(1); st.rerun()
                    except: st.error("Error al guardar.")

            st.write("---")
            try:
                res_inv = supabase.table("inventario_equipos").select("*").eq("clinica", nombre_c).order("ultima_actualizacion", desc=True).execute()
                if res_inv.data:
                    df_i = pd.DataFrame(res_inv.data).drop_duplicates(subset=['equipo'])
                    for _, r in df_i.iterrows():
                        colr = "🟢" if r['estado'] == "Operativo" else "🔴"
                        st.info(f"{colr} **{r['equipo']}**: {r['estado']}")
            except: pass

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

st.markdown("<p style='text-align: center; color: grey; font-size: 12px;'>BioData 2026 - Busca. Compara. Soluciona.</p>", unsafe_allow_html=True)
