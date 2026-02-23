import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import datetime
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 2. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="BioData", 
    page_icon="🔍", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 3. CSS PARA ESTÉTICA BIODATA
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; padding: 20px !important; border-radius: 15px !important; }
    [data-testid="stFileUploader"] label, [data-testid="stFileUploaderIcon"] { color: white !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; border-left: 10px solid #2E7D32; }
    .med-info-box h3, .med-info-box p, .med-info-box b { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; height: 3.5em !important; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .premium-card { border: 4px solid #FFD700 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 15px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; font-size: 1.1rem; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip())
                  if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")

col_a, col_b = st.columns(2)
with col_a:
    prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
with col_b:
    busqueda_manual = st.text_input("⌨️ Búsqueda manual (Opcional):", placeholder="Ej: Oct, Topografía...")

uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Por favor, sube una imagen o escribe el nombre del estudio.")
    else:
        try:
            # --- CARGA DE DATOS MULTI-HOJA ---
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            
            df.columns = df.columns.str.strip()
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'
            
            nombre_estudio = ""
            
            # --- DETERMINAR ESTUDIO ---
            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
            else:
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('🔍 BioData analizando orden médica...'):
                    response = model.generate_content(["Identifica el estudio médico. Responde SOLO el nombre.", img])
                    nombre_estudio = response.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # --- FILTRADO FLEXIBLE ---
            palabras_clave = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            def coincidencia_flexible(estudio_excel):
                est_limpio = limpiar_texto(str(estudio_excel))
                return any(p in est_limpio for p in palabras_clave)

            resultados = df[df['Estudio'].apply(coincidencia_flexible)].copy()

            if not resultados.empty:
                # --- GEOLOCALIZACIÓN BLINDADA ---
                geolocator = Nominatim(user_agent="biodata_v11")
                u_loc = geolocator.geocode(user_city)
                # Punto de origen (Usuario)
                lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                punto_usuario = (lat_i, lon_i)

                def geo_calc(row):
                    try:
                        dir_str = str(row['Direccion']).strip()
                        if not dir_str or dir_str == "nan": return 99.0
                        
                        loc = geolocator.geocode(dir_str)
                        if loc:
                            punto_clinica = (loc.latitude, loc.longitude)
                            # Validación final de formato para evitar el error de "arg must be list"
                            return round(geodesic(punto_usuario, punto_clinica).km, 1)
                        return 99.0
                    except:
                        return 99.0

                resultados['Km'] = resultados.apply(geo_calc, axis=1)
                resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                
                # SaaS Logic
                premium_df = resultados[resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                basic_df = resultados[~resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                
                col_res, col_mapa = st.columns([1, 1.5])
                
                with col_res:
                    fecha_hoy = datetime.date.today().strftime("%d/%m/%Y")
                    st.info(f"📅 Verificado: {fecha_hoy}")

                    for _, row in premium_df.iterrows():
                        wa = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                        url = f"https://wa.me/{wa}?text=Hola!%20Deseo%20agendar%20{nombre_estudio}"
                        st.markdown(f'<div class="premium-card"><p style="color:#B8860B; margin:0;">💎 PREMIUM</p><h3>{row["Nombre"]}</h3><h2>${int(row["Precio"])}</h2><p>📍 {row["Km"]} km</p><a href="{url}" class="btn-whatsapp" target="_blank">💬 AGENDAR</a></div>', unsafe_allow_html=True)

                    if not basic_df.empty:
                        m = basic_df.iloc[0]
                        wa_m = str(int(m['Whatsapp'])) if pd.notna(m['Whatsapp']) else ""
                        url_m = f"https://wa.me/{wa_m}?text=Info%20sobre%20{nombre_estudio}"
                        st.markdown(f'<div class="info-card"><h3>{m["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(m["Precio"])}</h2><p>📍 {m["Km"]} km</p><a href="{url_m}" class="btn-whatsapp" target="_blank">💬 CONSULTAR</a></div>', unsafe_allow_html=True)

                with col_mapa:
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                    folium.Marker([lat_i, lon_i], popup="Tú", icon=folium.Icon(color='red')).add_to(m)
                    folium_static(m)
                
                st.write("---")
                st.write("### 📋 Comparativa Completa")
                st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion', 'Redes Sociales']], use_container_width=True, hide_index=True)
            else:
                st.error(f"No hay sedes para '{nombre_estudio}'. Intenta con el buscador manual.")
        
        except Exception as e:
            st.error(f"Detalle técnico: {e}")
