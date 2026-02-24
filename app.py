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
    # Conexión a la base de datos Supabase
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
else:
    st.error("⚠️ Error: Faltan las llaves en los Secrets de Streamlit.")
    st.stop()

# --- 2. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData Business", page_icon="🔍", layout="wide")

st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    .stTextInput div div, .stSelectbox div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; padding: 20px !important; border-radius: 15px !important; color: white !important; }
    
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; width: 100%; border-radius: 10px !important; height: 3em; border: none !important; }

    .med-info-box { background-color: #1B5E20 !important; padding: 20px; border-radius: 15px; margin: 15px 0; border-left: 10px solid #2E7D32; }
    .med-info-box h3 { color: #FFFFFF !important; margin:0; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 15px; }
    .premium-card { border: 4px solid #D4AF37 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 15px; position: relative; }
    .premium-badge { background-color: #D4AF37; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.7rem; font-weight: 900; position: absolute; top: -15px; right: 20px; }
    
    .btn-share { background-color: #34B7F1 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES ---
def registrar_clic_real(clinica, estudio):
    """Guarda el interés en la tabla 'clics' de Supabase"""
    try:
        data = {"clinica": clinica, "estudio": estudio, "fecha": datetime.now().isoformat()}
        supabase.table("clics").insert(data).execute()
    except Exception as e:
        pass 

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

# --- 4. INTERFAZ ---
st.title("🔍 BioData")
u_city = st.text_input("📍 Tu ubicación actual:", "Caracas, Venezuela")

col_op1, col_op2 = st.columns(2)
with col_op1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True)
with col_op2: manual = st.text_input("⌨️ ¿Buscas un estudio específico?", placeholder="Ej: Eco abdominal...")

up_img = st.file_uploader("O sube foto de la orden", type=["jpg", "jpeg", "png"])

if st.button("🚀 ANALIZAR Y BUSCAR MEJORES OPCIONES"):
    if not up_img and not manual:
        st.warning("⚠️ Por favor, escribe un estudio o sube una imagen.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            if 'Plan' not in df.columns: df['Plan'] = 'Basico'

            nombre_estudio = manual.upper() if manual else ""
            if not manual:
                model = genai.GenerativeModel('models/gemini-flash-latest')
                with st.spinner('BioData IA analizando...'):
                    res = model.generate_content(["Dime solo el nombre del examen médico.", PIL.Image.open(up_img)])
                    nombre_estudio = res.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>📋 ESTUDIO DETECTADO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            kw = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in limpiar_texto(x) for k in kw))].copy()

            if not res_df.empty:
                geo = Nominatim(user_agent="biodata_app_v4")
                u_loc = geo.geocode(u_city)
                u_lat, u_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)

                kms, coords = [], []
                for _, row in res_df.iterrows():
                    d, c = 99.0, None
                    direccion = str(row.get('Direccion', '')).strip()
                    if direccion and direccion.lower() != 'nan':
                        try:
                            l = geo.geocode(direccion)
                            if l:
                                d = calcular_distancia(u_lat, u_lon, l.latitude, l.longitude)
                                c = [l.latitude, l.longitude]
                        except: pass
                    kms.append(d)
                    coords.append(c)

                res_df['Km'] = kms
                res_df['coords'] = coords
                res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)

                p_df = res_df[res_df['Plan'].str.capitalize() == 'Premium'].sort_values(by='Precio' if prio == "Precio" else 'Km')
                b_df = res_df[res_df['Plan'].str.capitalize() != 'Premium'].sort_values(by='Precio' if prio == "Precio" else 'Km')
                final_res = pd.concat([p_df, b_df])
                
                mejor = final_res.iloc[0]

                # REGISTRAR CLIC AUTOMÁTICAMENTE
                registrar_clic_real(mejor['Nombre'], nombre_estudio)

                col_izq, col_der = st.columns([1, 1.5])

                with col_izq:
                    estilo = "premium-card" if mejor['Plan'].capitalize() == 'Premium' else "info-card"
                    badge = '<div class="premium-badge">⭐ RECOMENDADO</div>' if mejor['Plan'].capitalize() == 'Premium' else ""
                    
                    st.markdown(f'''
                        <div class="{estilo}">
                            {badge}
                            <p style="margin:0; color:#1B5E20; font-size:0.8rem;">MEJOR OPCIÓN</p>
                            <h2 style="margin:5px 0;">{mejor["Nombre"]}</h2>
                            <h1 style="color: #1B5E20; margin: 5px 0;">${int(mejor["Precio"])}</h1>
                            <p style="margin:0;">📍 Distancia: {mejor["Km"]} km</p>
                        </div>
                    ''', unsafe_allow_html=True)

                    if 'Whatsapp' in mejor and not pd.isna(mejor['Whatsapp']):
                        wa = str(mejor['Whatsapp']).split('.')[0]
                        url_wa = f"https://wa.me/{wa}?text=Hola,%20vengo%20de%20BioData.%20Cita%20para:%20{nombre_estudio}"
                        
                        st.markdown(f'''
                            <a href="{url_wa}" target="_blank" style="text-decoration: none;">
                                <div style="background-color: #25D366; color: white; padding: 15px; text-align: center; border-radius: 10px; font-weight: 900; cursor: pointer;">
                                    💬 AGENDAR EN {mejor['Nombre']}
                                </div>
                            </a>
                        ''', unsafe_allow_html=True)

                    share_t = f"BioData: {nombre_estudio} en {mejor['Nombre']} por ${int(mejor['Precio'])}"
                    st.markdown(f'<a href="https://wa.me/?text={share_t}" class="btn-share" target="_blank">📲 COMPARTIR</a>', unsafe_allow_html=True)

                with col_der:
                    m = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                    folium.Marker([u_lat, u_lon], popup="Tú", icon=folium.Icon(color='red')).add_to(m)
                    for _, r in final_res.iterrows():
                        if r['coords']:
                            c = 'orange' if r['Plan'].capitalize() == 'Premium' else 'blue'
                            folium.Marker(r['coords'], popup=r['Nombre'], icon=folium.Icon(color=c)).add_to(m)
                    folium_static(m)

                st.write("### 🏥 Todas las sedes encontradas:")
                st.dataframe(final_res[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)

            else:
                st.error("No se encontraron sedes para este estudio.")
        except Exception as e:
            st.error(f"Error técnico: {e}")

# --- 5. PANEL ADMIN ---
st.write("---")
if st.checkbox("📊 Ver Estadísticas"):
    try:
        res_db = supabase.table("clics").select("*").execute()
        stats_df = pd.DataFrame(res_db.data)
        if not stats_df.empty:
            st.success(f"✅ Total derivaciones: {len(stats_df)}")
            chart_data = stats_df['clinica'].value_counts()
            st.bar_chart(chart_data)
        else:
            st.info("La tabla 'clics' existe pero aún no tiene datos.")
    except Exception as e:
        st.warning("Aún no se pueden cargar las estadísticas. Asegúrate de que la tabla 'clics' esté lista.")
