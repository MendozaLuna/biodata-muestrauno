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
    .pro-card { border: 3px solid #1B5E20 !important; border-radius: 15px; padding: 30px; background-color: #F0F9F0; margin-bottom: 10px; text-align: center; }
    .standard-card { border: 2px solid #808080 !important; border-radius: 15px; padding: 30px; background-color: #F9F9F9; margin-bottom: 10px; text-align: center; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 15px; font-size: 1.1rem; }
    .btn-share { background-color: #34B7F1 !important; color: white !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; font-size: 1.1rem; }
    .suggestion-box { background-color: #E8F5E9; padding: 20px; border-radius: 15px; border: 2px dashed #1B5E20; margin-top: 30px; }
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
                loc_manual = geo.geocode(u_city)
                c_lat, c_lon = (loc_manual.latitude, loc_manual.longitude) if loc_manual else (10.48, -66.90)
            
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
                
                # --- LÓGICA DE CLASIFICACIÓN POR PLAN ---
                def definir_estilo(row):
                    p = str(row.get('Plan', 'Basico')).strip().capitalize()
                    if p == "Premium": return "premium-card", "💎 ALIADO PREMIUM", "#D4AF37", 1
                    if p == "Pro": return "pro-card", "✅ SEDE PRO", "#1B5E20", 2
                    return "standard-card", "📍 SEDE BÁSICA", "#808080", 3

                res_df['Estilo_Datos'] = res_df.apply(definir_estilo, axis=1)
                res_df['Orden_Plan'] = res_df['Estilo_Datos'].apply(lambda x: x[3])
                
                # Ordenar por Plan y luego por la prioridad elegida
                final = res_df.sort_values(by=['Orden_Plan', 'Precio' if prio == "Precio" else 'Km'])
                mejor = final.iloc[0]
                card_class, badge_text, badge_color, _ = mejor['Estilo_Datos']
                
                col_i, col_m = st.columns([1, 1])
                with col_i:
                    st.markdown(f"""
                        <div class="{card_class}">
                            <p style="color: {badge_color}; font-size: 0.9rem; margin: 0; font-weight: 900;">{badge_text}</p>
                            <h2 style="color: #1B5E20; margin: 0;">{mejor['Nombre']}</h2>
                            <h1 style="font-size: 3.5rem; margin: 10px 0;">${int(mejor['Precio'])}</h1>
                            <p>📍 A {mejor['Km']} km</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    wa_num = str(mejor.get('Whatsapp', '584120000000')).split('.')[0]
                    st.markdown(f'<a href="https://wa.me/{wa_num}?text=Consulta BioData" target="_blank" class="btn-wa">📱 CONTACTAR AHORA</a>', unsafe_allow_html=True)
                    
                    t_share = f"*BioData*: {mejor['Nombre']} ofrece {n_est} por ${int(mejor['Precio'])}."
                    st.markdown(f'<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(t_share)}" target="_blank" class="btn-share">🔗 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)
                
                with col_m: folium_static(m_folium, width=500, height=400)
                
                st.write("---")
                st.write("### 🏥 Todas las sedes disponibles:")
                tabla_v = final[['Nombre', 'Precio', 'Km', 'Direccion', 'Plan']].copy()
                tabla_v.columns = ['Sede', 'Precio ($)', 'Distancia (Km)', 'Ubicación', 'Plan']
                st.dataframe(tabla_v, use_container_width=True, hide_index=True)

                st.markdown('<div class="suggestion-box">', unsafe_allow_html=True)
                st.subheader("¿No encuentras tu clínica?")
                cs1, cs2 = st.columns(2)
                sn_p = cs1.text_input("Nombre Clínica:", key="sn_p")
                sz_p = cs2.text_input("Zona:", key="sz_p")
                if st.button("📩 ENVIAR SUGERENCIA", key="send_sug_p"): 
                    if sn_p and sz_p: enviar_sugerencia(sn_p, sz_p)
                st.markdown('</div>', unsafe_allow_html=True)
            else: st.error("No se encontraron sedes.")
        except Exception as e: st.error(f"Error: {e}")

# --- 7. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Clínicas")
    clave = st.text_input("Clave de Acceso", type="password", key="pass_e")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        
        # Banner de Upgrade para Pro y Basico
        if nombre_c != "ADMIN":
            st.info(f"🚀 **{nombre_c}**, ¿quieres más visibilidad? El **Plan Premium** te posiciona en el Top 1.")
            if st.button("💎 SOLICITAR UPGRADE", key="btn_upgrade"):
                st.balloons()
                st.write("✅ Solicitud enviada. Un asesor te contactará para subir a Premium.")

        tab_stats, tab_sug = st.tabs(["📊 Estadísticas", "📩 Sugerencias"])
        
        with tab_stats:
            c_f1, c_f2 = st.columns(2)
            with c_f1: f_ini = st.date_input("Desde:", date.today() - timedelta(days=7), key="stats_desde")
            with c_f2: f_fin = st.date_input("Hasta:", date.today(), key="stats_hasta")

            try:
                resp = supabase.table("busquedas_stats").select("*").execute()
                df_full = pd.DataFrame(resp.data)
                
                if not df_full.empty:
                    df_full['fecha_dt'] = pd.to_datetime(df_full['fecha'], errors='coerce').dt.tz_localize(None)
                    start_limit = pd.Timestamp(f_ini)
                    end_limit = pd.Timestamp(f_fin) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    df_stats = df_full[(df_full['fecha_dt'] >= start_limit) & (df_full['fecha_dt'] <= end_limit)].copy()
                    
                    if not df_stats.empty:
                        st.metric("Búsquedas en periodo", len(df_stats))
                        
                        # --- GRÁFICA MULTICOLOR ---
                        top_data = df_stats['estudio'].value_counts().head(5).reset_index()
                        top_data.columns = ['estudio', 'conteo']
                        chart = alt.Chart(top_data).mark_bar().encode(
                            x=alt.X('estudio', sort='-y', title='Estudios'),
                            y=alt.Y('conteo', title='Cantidad'),
                            color=alt.Color('estudio', legend=None, scale=alt.Scale(scheme='category10'))
                        ).properties(height=400)
                        st.altair_chart(chart, use_container_width=True)
                        
                        # --- EXPORTACIÓN A EXCEL ---
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            df_stats.to_excel(writer, index=False, sheet_name='Reporte_BioData')
                        st.download_button(
                            label="📥 Descargar Reporte en Excel",
                            data=buffer.getvalue(),
                            file_name=f"BioData_{f_ini}_{f_fin}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="btn_excel"
                        )
                        
                        st.write("---")
                        st.subheader("📍 Mapa de Calor")
                        puntos = df_stats[['lat', 'lon']].dropna().values.tolist()
                        m_h = folium.Map(location=[10.48, -66.90], zoom_start=11)
                        HeatMap(puntos).add_to(m_h)
                        folium_static(m_h, width=1000, height=500)
                    else:
                        st.warning(f"No hay registros entre {f_ini} y {f_fin}.")
            except Exception as e: st.error(f"Error en estadísticas: {e}")
            
        with tab_sug:
            try:
                s_res = supabase.table("sugerencias").select("*").execute()
                if s_res.data: st.table(pd.DataFrame(s_res.data)[['clinica', 'zona', 'fecha']])
                else: st.info("No hay sugerencias.")
            except: st.info("Módulo activo.")
