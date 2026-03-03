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

    div.stButton > button p { color: #FFFFFF !important; font-weight: 700 !important; }

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

    .premium-card h1, .premium-card h2, .premium-card p,
    .pro-card h1, .pro-card h2, .pro-card p,
    .standard-card h1, .standard-card h2, .standard-card p { 
        color: #101828 !important; 
    }
    
    .premium-card { background-color: #FFFDF0 !important; border: 1px solid #D4AF37 !important; }
    .pro-card { background-color: #F0FDF4 !important; border: 1px solid #26A69A !important; }
    .standard-card { background-color: #FFFFFF !important; border: 1px solid #E4E7EC !important; }

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
    prompt = f"Escribe un copy publicitario corto y persuasivo para Instagram/WhatsApp de una clínica oftalmológica. Oferta: {estudio} por solo ${precio}. Incluye emojis."
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

    if st.button("🚀 BUSCAR MEJORES OPCIONES", key="main_search") or 'final_df' in st.session_state:
        try:
            # Solo procesamos si hay una nueva búsqueda
            if st.button("🚀 BUSCAR MEJORES OPCIONES", key="hidden_search", help="hidden"): 
                st.session_state.pop('final_df', None)

            if 'final_df' not in st.session_state:
                df = pd.read_excel("base_clinicas.xlsx")
                df.columns = [str(c).strip().capitalize() for c in df.columns]

                try:
                    inv_resp = supabase.table("inventario_equipos").select("clinica, equipo, estado").order("ultima_actualizacion", desc=True).execute()
                    df_inv_global = pd.DataFrame(inv_resp.data).drop_duplicates(subset=['clinica', 'equipo'])
                except:
                    df_inv_global = pd.DataFrame(columns=['clinica', 'equipo', 'estado'])

                with st.spinner('Analizando estudio...'):
                    if manual: n_est, d_est = analizar_texto_ai(manual)
                    elif up_img: n_est, d_est = analizar_imagen_ai(up_img.getvalue())
                    else: st.warning("Escribe el examen."); st.stop()
                    st.session_state.n_est = n_est
                    st.session_state.d_est = d_est
                
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
                        match = df_inv_global[(df_inv_global['clinica'] == clinica_nom) & (df_inv_global['equipo'].apply(lambda x: x.lower() in est_nom.lower()))]
                        return match.iloc[0]['estado'] == "Operativo" if not match.empty else True
                    
                    res_df['Disponible'] = res_df.apply(lambda r: esta_operativo(r['Nombre'], n_est), axis=1)
                    res_df = res_df[res_df['Disponible'] == True].copy()

                    kms = []
                    lats, lons = [], []
                    for _, row in res_df.iterrows():
                        d, lt, ln = 99.0, 0.0, 0.0
                        try:
                            l = geo.geocode(str(row.get('Direccion','')))
                            if l: 
                                d = calcular_distancia(c_lat, c_lon, l.latitude, l.longitude)
                                lt, ln = l.latitude, l.longitude
                        except: pass
                        kms.append(d); lats.append(lt); lons.append(ln)
                    
                    res_df['Km'] = kms
                    res_df['lat'] = lats
                    res_df['lon'] = lons
                    res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                    
                    def definir_estilo(row):
                        p = str(row.get('Plan', 'Básico')).strip().capitalize()
                        if p == "Premium": return "premium-card", "💎 ALIADO PREMIUM", "#D4AF37", 1
                        if p == "Pro": return "pro-card", "✅ SEDE PRO", "#00796B", 2
                        return "standard-card", "📍 SEDE BÁSICA", "#808080", 3

                    res_df['Estilo_Datos'] = res_df.apply(definir_estilo, axis=1)
                    res_df['Orden_Plan'] = res_df['Estilo_Datos'].apply(lambda x: x[3])
                    st.session_state.final_df = res_df.sort_values(by=['Orden_Plan', 'Precio' if prio == "Precio" else 'Km'])

            # --- VISUALIZACIÓN INTERACTIVA ---
            if 'final_df' in st.session_state and not st.session_state.final_df.empty:
                final = st.session_state.final_df
                st.markdown(f'''<div class="med-info-box"><h4>📋 {st.session_state.n_est}</h4><p>{st.session_state.d_est}</p></div>''', unsafe_allow_html=True)
                
                st.subheader("🏥 Sedes encontradas")
                st.info("💡 Haz clic en una fila para actualizar el detalle y el mapa.")
                
                # Tabla interactiva
                event = st.dataframe(
                    final[['Nombre', 'Precio', 'Ciudad', 'Km']], 
                    use_container_width=True, 
                    hide_index=True, 
                    on_select="rerun", 
                    selection_mode="single-row", 
                    key="tabla_p"
                )

                # Definimos 'mejor' según el clic o por defecto la primera fila
                if event and len(event["selection"]["rows"]) > 0:
                    mejor = final.iloc[event["selection"]["rows"][0]]
                else:
                    mejor = final.iloc[0]

                # Estilos de la tarjeta
                card_class, badge_text, badge_color, _ = mejor['Estilo_Datos']
                
                col_i, col_m = st.columns([1, 1])
                
                with col_i:
                    # Forzamos colores oscuros para que no se vean blancos en fondo claro
                    st.markdown(f"""
                        <div class="{card_class}" style="padding: 20px; border-radius: 20px; border: 2px solid {badge_color};">
                            <div class="status-badge" style="background-color:#E8F5E9; color:#2E7D32;">✔ DISPONIBLE</div>
                            <p style="color:{badge_color}; font-weight:900; margin:0;">{badge_text}</p>
                            <h2 style="color:#101828 !important; margin:5px 0; font-size:1.8rem;">{mejor['Nombre']}</h2>
                            <h1 style="color:#101828 !important; margin:10px 0; font-size:3rem;">${int(mejor['Precio'])}</h1>
                            <p style="color:#475467 !important; font-size:1.1rem; font-weight:600;">📍 {mejor.get('Ciudad','')} — A {mejor['Km']} km</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # WhatsApp dinámico
                    wa_num = str(mejor.get('Whatsapp', '584120000000')).replace('+', '').split('.')[0]
                    texto_wa = urllib.parse.quote(f"Hola {mejor['Nombre']}, consulto disponibilidad de {st.session_state.n_est} vía BioData.")
                    st.markdown(f'''
                        <a href="https://wa.me/{wa_num}?text={texto_wa}" target="_blank" class="btn-wa" style="text-decoration:none;">
                            📱 CONTACTAR POR WHATSAPP
                        </a>
                    ''', unsafe_allow_html=True)
                
                with col_m:
                    # Forzamos coordenadas válidas para el mapa
                    lat_map = mejor['lat'] if mejor['lat'] != 0 else 10.48
                    lon_map = mejor['lon'] if mejor['lon'] != 0 else -66.90
                    
                    m = folium.Map(location=[lat_map, lon_map], zoom_start=15, control_scale=True)
                    folium.Marker(
                        [lat_map, lon_map], 
                        tooltip=mejor['Nombre'],
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(m)
                    folium_static(m, width=500, height=400)
            else:
                st.error("No se encontraron sedes para este estudio.")
        except Exception as e:
            st.error(f"Error: {e}")

# --- 7. CONTENIDO EMPRESA (Portal de Gestión) ---
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

        if nombre_c == "ADMIN" or "Premium" in clave:
                st.subheader("📊 Cuadro de Market Share")
                
                # 1. Selector con opción manual
                opciones_base = ["OCT de Mácula", "Campimetría (Campo Visual)", "Ecografía Ocular", "Topografía", "Otro (Ingreso manual)..."]
                sel_temp = st.selectbox("Seleccione el estudio para comparar:", opciones_base, key="sel_market_share")

                # 2. Lógica para el ingreso manual
                if sel_temp == "Otro (Ingreso manual)...":
                    estudio_sel = st.text_input("Escriba el nombre del estudio a analizar:", placeholder="Ej: Paquimetría...", key="manual_market_share")
                else:
                    estudio_sel = sel_temp

                # Solo mostramos el análisis si hay un nombre definido
                # --- CÁLCULO MATEMÁTICO CORREGIDO ---
                    precio_tu = 75  # Tu precio actual
                    precio_comp = 70 # Precio base de competencia
                    
                    # Fórmula: ((Nuevo - Base) / Base) * 100
                    # Esto nos dice cuánto POR ENCIMA o DEBAJO estás de la competencia
                    dif_precio = ((precio_tu - precio_comp) / precio_comp) * 100

                    m_data = {
                        "Indicador": [f"Precio {estudio_sel}", "T. Respuesta", "Clicks/100"],
                        "Tu Clínica": [f"${precio_tu}", "< 5 min", "12"],
                        "Competencia": [f"${precio_comp}", "15 min", "25"],
                        "Dif.": ["🔴 +21%(Por Encima)", "🟢 -66%(Excelente)", "🔴 -52%(Por Debajo)"]}
                    
                    st.table(pd.DataFrame(m_data))

                    # 3. Recomendación dinámica
                    st.markdown(f"""
                        <div style="background-color: #E8F5E9; padding: 20px; border-radius: 10px; border-left: 5px solid #1B5E20;">
                            <h4 style="color: #1B5E20 !important; margin-top: 0;">🧠 Recomendación Estratégica</h4>
                            <p style="color: #1B5E20 !important;">
                                Para el análisis de <b>{estudio_sel}</b>, los datos indican que tu clínica está 
                                {'perdiendo competitividad en precio' if dif_precio > 0 else 'en una posición sólida'}.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.subheader("📍 Mapa de Calor de Demanda")
                try:
                    resp = supabase.table("busquedas_stats").select("lat, lon").execute()
                    pts = pd.DataFrame(resp.data).dropna().values.tolist()
                    m_p = folium.Map(location=[10.48, -66.90], zoom_start=11)
                    if pts: 
                        HeatMap(pts).add_to(m_p)
                        folium_static(m_p)
                except: 
                    st.info("Cargando mapa de demanda...")
        else:
                st.error("🔒 Esta función es exclusiva para el Plan PREMIUM.")

        with tab_oferta:
            st.subheader("⚡ Crear Oferta Relámpago")
            if nombre_c == "ADMIN" or "Pro" in clave or "Premium" in clave:
                c1, c2 = st.columns(2)
                opciones = ["OCT de Mácula", "Campimetría", "Topografía", "Otro (Escribir manual)..."]
                sel_temp = c1.selectbox("Estudio:", opciones, key="sel_estudio_oferta")
                
                if sel_temp == "Otro (Escribir manual)...": 
                    estudio_final = c1.text_input("Escriba el nombre del estudio:", key="input_manual_oferta")
                else: 
                    estudio_final = sel_temp
                
                precio_of = c2.number_input("Precio ($):", min_value=1, value=50, key="precio_oferta")
                
                if st.button("🪄 GENERAR CON IA", key="btn_gen_ia"):
                    if estudio_final:
                        with st.spinner("Generando copy persuasivo..."):
                            try:
                                copy_generado = generar_copy_oferta(estudio_final, precio_of)
                                st.markdown("### 📝 Tu oferta lista para usar:")
                                st.info(copy_generado)
                                st.caption("Copia y pega este texto en tu WhatsApp o Instagram.")
                            except Exception as e:
                                st.error(f"Hubo un problema con la IA: {e}")
                    else: st.warning("⚠️ Por favor, ingresa o selecciona un estudio primero.")
            else: st.warning("🔒 Esta función requiere un Plan PRO o PREMIUM.")

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
                        st.success("✅ Estado actualizado."); time.sleep(1); st.rerun()
                    except: st.error("Error al guardar.")

            st.write("---")
            try:
                res_inv = supabase.table("inventario_equipos").select("*").eq("clinica", nombre_c).order("ultima_actualizacion", desc=True).execute()
                if res_inv.data:
                    df_i = pd.DataFrame(res_inv.data).drop_duplicates(subset=['equipo'])
                    for _, r in df_i.iterrows():
                        colr = "🟢" if r['estado'] == "Operativo" else "🔴"
                        st.info(f"{colr} *{r['equipo']}*: {r['estado']}")
            except: pass

# --- 8. PIE DE PÁGINA ---
st.markdown("---")
with st.form("buzon_final", clear_on_submit=True):
    st.subheader("📩 Buzón de Sugerencias")
    mensaje_b = st.text_area("Tu comentario:")
    if st.form_submit_button("Enviar a BioData"):
        if mensaje_b: st.success("✅ Recibido.")
st.markdown("<p style='text-align: center; color: grey; font-size: 12px;'>BioData 2026 - Busca. Compara. Soluciona.</p>", unsafe_allow_html=True)
