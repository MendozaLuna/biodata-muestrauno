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
    .premium-card { border: 5px solid #D4AF37 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 10px; position: relative; text-align: center; }
    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; font-size: 0.9rem; }
    .btn-share { background-color: #34B7F1 !important; color: white !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 5px; font-size: 0.9rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. LÓGICA DE NAVEGACIÓN ---
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

# --- 5. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"): st.session_state.perfil = None; st.rerun()

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

    st.title("🔍 Buscador de Estudios")
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

                # 1. RESULTADO DETECTADO
                st.markdown(f'''<div class="med-info-box"><h4>📋 {nombre_estudio}</h4><p>{descripcion_estudio}</p></div>''', unsafe_allow_html=True)

                palabras_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
                res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in limpiar_texto(x) for k in palabras_clave))].copy()

                if not res_df.empty:
                    geo = Nominatim(user_agent="biodata_geo_final")
                    u_loc = geo.geocode(u_city)
                    u_lat, u_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    kms = []
                    m_folium = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                    folium.Marker([u_lat, u_lon], tooltip="Tú", icon=folium.Icon(color='blue')).add_to(m_folium)

                    for _, row in res_df.iterrows():
                        d = 99.0
                        try:
                            l = geo.geocode(str(row.get('Direccion','')))
                            if l: 
                                d = calcular_distancia(u_lat, u_lon, l.latitude, l.longitude)
                                folium.Marker([l.latitude, l.longitude], tooltip=row['Nombre'], icon=folium.Icon(color='green' if str(row['Plan']).capitalize() == 'Premium' else 'gray')).add_to(m_folium)
                        except: pass
                        kms.append(d)
                    
                    res_df['Km'] = kms
                    res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)
                    final_res = res_df.sort_values(by='Precio' if prio == "Precio" else 'Km')
                    mejor = final_res.iloc[0]
                    registrar_clic_real(mejor['Nombre'], nombre_estudio)

                    # 2. SECCIÓN DIVIDIDA: MAPA (IZQ) Y MEJOR OPCIÓN (DER)
                    col_mapa, col_info = st.columns([1.8, 1])
                    
                    with col_mapa:
                        folium_static(m_folium, width=700)

                    with col_info:
                        st.markdown(f'''
                            <div class="premium-card">
                                <p style="color: #D4AF37; font-size: 0.8rem; margin-bottom: 5px;">⭐ MEJOR OPCIÓN</p>
                                <h3 style="margin: 0; color: #1B5E20;">{mejor["Nombre"]}</h3>
                                <h1 style="margin: 10px 0; color: #000;">${int(mejor["Precio"])}</h1>
                                <p style="font-size: 0.9rem;">📍 A {mejor["Km"]} km de distancia</p>
                            </div>
                        ''', unsafe_allow_html=True)
                        
                        # Botones de Agendar y Compartir
                        if 'Whatsapp' in mejor and not pd.isna(mejor['Whatsapp']):
                            wa_num = str(mejor['Whatsapp']).split('.')[0]
                            url_wa = f"https://wa.me/{wa_num}?text=Cita%20BioData:%20{nombre_estudio}"
                            st.markdown(f'<a href="{url_wa}" target="_blank" class="btn-wa">💬 AGENDAR CITA</a>', unsafe_allow_html=True)
                            
                            share_text = f"Mira esta opción: {mejor['Nombre']} tiene {nombre_estudio} por ${int(mejor['Precio'])}."
                            st.markdown(f'<a href="https://api.whatsapp.com/send?text={share_text}" target="_blank" class="btn-share">📢 COMPARTIR OPCIÓN</a>', unsafe_allow_html=True)

                    st.write("---")
                    st.write("### 🏥 Todas las sedes disponibles:")
                    st.dataframe(final_res[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)
                else: st.error("No se encontraron sedes.")
            except Exception as e: st.error(f"Error: {e}")

# --- 6. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="v_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Clínicas")
    clave = st.text_input("Introduce tu clave de Aliado", type="password")
    if clave in ACCESOS_CLINICAS:
        nombre_clinica = ACCESOS_CLINICAS[clave]
        try:
            res_db = supabase.table("clics").select("*").execute()
            df_clics = pd.DataFrame(res_db.data)
            if not df_clics.empty:
                stats_vista = df_clics if nombre_clinica == "ADMIN" else df_clics[df_clics['clinica'] == nombre_clinica]
                st.success(f"👋 ¡Hola {nombre_clinica}!")
                c1, c2 = st.columns(2)
                with c1: st.metric("Pacientes Derivados", len(stats_vista))
                with c2: 
                    if not stats_vista.empty: st.metric("Servicio Líder", stats_vista['estudio'].value_counts().idxmax())
                if not stats_vista.empty:
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        stats_vista['fecha_dt'] = pd.to_datetime(stats_vista['fecha']).dt.date
                        st.line_chart(stats_vista['fecha_dt'].value_counts().sort_index())
                    with col_g2: st.bar_chart(stats_vista['estudio'].value_counts())
                    csv = stats_vista[['fecha', 'estudio']].to_csv(index=False).encode('utf-8')
                    st.download_button("📊 Descargar Reporte", csv, f'reporte_{nombre_clinica}.csv', 'text/csv')
            else: st.info("Sin datos.")
        except Exception as e: st.error(f"Error: {e}")
