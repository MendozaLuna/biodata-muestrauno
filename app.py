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
import io
import altair as alt
import time
import streamlit.components.v1 as components
from folium.features import DivIcon

# --- 1. CONFIGURACIÓN Y SEGURIDAD ---
st.set_page_config(page_title="BioData 2026", page_icon="🏥", layout="wide")

if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
else:
    st.error("Credenciales no detectadas.")
    st.stop()

# --- 2. ACCESOS ---
ACCESOS_CLINICAS = {"AdminBio2026": "ADMIN", "ClinisacPremium26": "Clinisac", "PampatarPremium26": "Salud Visual Margarita", "OftalmoPlus26": "Oftalmo Plus"}

# --- 3. FUNCIONES TÉCNICAS ---
def calcular_distancia(la1, lo1, la2, lo2):
    R = 6371.0
    dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)

def analizar_texto_ai(texto):
    model = genai.GenerativeModel('gemini-1.5-flash')
    res = model.generate_content(f"Define brevemente: {texto}. Max 15 palabras.")
    return texto.upper(), res.text

def generar_copy_oferta(estudio, precio):
    model = genai.GenerativeModel('gemini-1.5-flash')
    res = model.generate_content(f"Copy publicitario para {estudio} a ${precio}. Corto, emojis.")
    return res.text

# --- 4. NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown("<h1 style='text-align:center; color:#004D40; font-size:4rem;'>BioData</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; font-size:1.5rem;'>Conecta. Explora. Soluciona.</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("👤 PACIENTE", use_container_width=True): st.session_state.perfil = 'persona'; st.rerun()
    with c2: 
        if st.button("🏥 EMPRESA", use_container_width=True): st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 5. LÓGICA PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    
    st.title("🔍 Buscador de Estudios")
    u_city = st.text_input("Ubicación:", "Caracas")
    manual = st.text_input("¿Qué examen buscas?")
    prio = st.radio("Prioridad:", ["Precio", "Cercanía"], horizontal=True)

    if st.button("🚀 Buscar"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            n_est, _ = analizar_texto_ai(manual)
            st.session_state.n_est_guardado = n_est
            
            geo = Nominatim(user_agent="biodata_26")
            loc = geo.geocode(f"{u_city}, Venezuela")
            lat_u, lon_u = (loc.latitude, loc.longitude) if loc else (10.48, -66.90)
            st.session_state.u_lat, st.session_state.u_lon = lat_u, lon_u
            
            supabase.table("busquedas_stats").insert({"lat": lat_u, "lon": lon_u, "estudio": n_est, "fecha": datetime.now().isoformat()}).execute()

            def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
            palabras = [p for p in norm(n_est).split() if len(p) > 2]
            res = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()
            
            if not res.empty:
                res['Km'] = res.apply(lambda r: calcular_distancia(lat_u, lon_u, r['Latitud'], r['Longitud']), axis=1)
                res['Prio_Plan'] = res['Plan'].map({"Premium": 0, "Pro": 1, "Básico": 2}).fillna(2)
                res = res.sort_values(['Prio_Plan', 'Precio' if prio == "Precio" else 'Km'])
                st.session_state.df_res = res
        except Exception as e: st.error(f"Error: {e}")

    if 'df_res' in st.session_state:
        df_res = st.session_state.df_res
        sel = st.dataframe(df_res[['Nombre', 'Precio', 'Km', 'Plan']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        idx_fila = sel.selection.rows[0] if sel.selection.rows else 0
        mostrar = df_res.iloc[idx_fila]

        # --- TARJETA VISUAL (TU LÓGICA ORIGINAL) ---
        plan = str(mostrar.get('Plan', 'Básico')).strip().capitalize()
        colores = {"Premium": ("#FFFDF0", "#D4AF37", "#B8860B", "💎 ALIADO PREMIUM"), "Pro": ("#F5F5F5", "#C0C0C0", "#708090", "✅ SEDE PRO")}
        bg, brd, txt, lbl = colores.get(plan, ("#E3F2FD", "#2196F3", "#1976D2", "📍 SEDE BÁSICA"))

        st.markdown(f"""<div style="background:{bg}; padding:20px; border-radius:15px; border:2px solid {brd}; text-align:center;">
            <p style="color:{txt}; font-weight:800; font-size:12px;">{lbl}</p>
            <h2>{mostrar['Nombre']}</h2><h1>${int(mostrar['Precio'])}</h1>
            <p>📍 A {mostrar['Km']} km de ti</p></div>""", unsafe_allow_html=True)

        # BOTONES Y WHATSAPP
        wa_num = str(mostrar.get('Whatsapp', '584120000000')).split('.')[0]
        est_n = st.session_state.n_est_guardado
        msg_c = urllib.parse.quote(f"Hola, busco {est_n} en {mostrar['Nombre']}. Vi el precio de ${mostrar['Precio']} en BioData.")
        msg_fam = urllib.parse.quote(f"🏥 OPCIÓN BIODATA\n🔬 {est_n}\n📍 {mostrar['Nombre']}\n💰 ${mostrar['Precio']}\n📱 https://wa.me/{wa_num}")
        g_maps = f"https://www.google.com/maps/dir/?api=1&destination={mostrar['Latitud']},{mostrar['Longitud']}"

        h_btns = f"""<div style="display:flex; flex-direction:column; gap:8px; margin-top:10px;">
            <a href="https://wa.me/{wa_num}?text={msg_c}" target="_blank" style="text-decoration:none; background:#25D366; color:white; padding:12px; border-radius:50px; text-align:center; font-weight:700;">CONTACTAR</a>
            <a href="https://api.whatsapp.com/send?text={msg_fam}" target="_blank" style="text-decoration:none; border:2px solid #00796B; color:#00796B; padding:10px; border-radius:50px; text-align:center;">COMPARTIR</a>
            <a href="{g_maps}" target="_blank" style="text-decoration:none; background:#4285F4; color:white; padding:12px; border-radius:50px; text-align:center; font-weight:700;">MAPS</a></div>"""
        components.html(h_btns, height=220)

# --- 6. PORTAL EMPRESA (COMPLETO) ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"): st.session_state.perfil = None; st.rerun()
    clave = st.text_input("Clave:", type="password")
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        t_stats, t_pre, t_of, t_inv = st.tabs(["📊 Stats", "💎 Premium", "⚡ Oferta", "🛠️ Inventario"])
        
        with t_stats:
            res_s = supabase.table("busquedas_stats").select("*").execute()
            df_s = pd.DataFrame(res_s.data)
            if not df_s.empty:
                st.metric("Consultas", len(df_s))
                top = df_s['estudio'].str.upper().value_counts().head(5).reset_index()
                st.altair_chart(alt.Chart(top).mark_bar().encode(x='estudio', y='count', color='estudio'), use_container_width=True)

        with t_pre:
            if "Premium" in clave or nombre_c == "ADMIN":
                st.subheader("Análisis Estratégico")
                df_all = pd.read_excel("base_clinicas.xlsx")
                df_all.columns = [str(c).strip().capitalize() for c in df_all.columns]
                
                # Market Share
                share = df_all.groupby('Nombre').size().reset_index(name='Sedes')
                fig = alt.Chart(share).mark_arc(innerRadius=50).encode(theta='Sedes', color='Nombre')
                st.altair_chart(fig, use_container_width=True)
                
                # Mapa de Calor
                pts = [[r['lat'], r['lon']] for r in res_s.data if r.get('lat')]
                m = folium.Map(location=[10.48, -66.90], zoom_start=11)
                HeatMap(pts).add_to(m)
                folium_static(m)
                st.info("🌡️ Las zonas rojas son pacientes sin cobertura cercana.")
            else: st.error("Requiere Plan Premium")

        with t_of:
            est_p = st.text_input("Estudio:")
            pre_p = st.number_input("Precio:", 1)
            if st.button("Crear Anuncio"): st.info(generar_copy_oferta(est_p, pre_p))

        with t_inv:
            eq_inv = st.selectbox("Equipo:", ["OCT", "Retinógrafo", "Campímetro"])
            st_inv = st.radio("Estado:", ["Operativo", "Mantenimiento"])
            if st.button("Actualizar"):
                supabase.table("inventario_equipos").insert({"clinica": nombre_c, "equipo": eq_inv, "estado": st_inv, "ultima_actualizacion": datetime.now().isoformat()}).execute()
                st.success("Estado actualizado.")
