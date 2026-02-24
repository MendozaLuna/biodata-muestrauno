import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
import math
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 2. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="BioData Premium", page_icon="🔍", layout="wide")

# 3. CSS PREMIUM (Colores Verde BioData y Dorado Premium)
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    .med-info-box { background-color: #1B5E20 !important; padding: 20px; border-radius: 15px; margin: 15px 0; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; margin:0; }

    /* Tarjeta Normal */
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 15px; }
    
    /* Tarjeta Premium */
    .premium-card { border: 4px solid #D4AF37 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 15px; position: relative; }
    .premium-badge { background-color: #D4AF37; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.7rem; font-weight: 900; position: absolute; top: -15px; right: 20px; }

    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    .btn-share { background-color: #34B7F1 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE APOYO ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    try:
        R = 6371.0 
        dlat, dlon = math.radians(float(lat2)-float(lat1)), math.radians(float(lon2)-float(lon1))
        a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
        return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)
    except: return 99.0

def limpiar(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
u_city = st.text_input("📍 Tu ubicación actual:", "Caracas, Venezuela")

col_p1, col_p2 = st.columns(2)
with col_p1: prio = st.radio("Ordenar resultados por:", ("Precio", "Ubicación"), horizontal=True)
with col_p2: manual = st.text_input("⌨️ ¿Buscas un estudio específico?", placeholder="Ej: Eco, Perfil 20...")

up_img = st.file_uploader("O sube la foto de tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🚀 ANALIZAR Y BUSCAR MEJORES OPCIONES"):
    if not up_img and not manual:
        st.warning("⚠️ Por favor, ingresa un nombre o sube una imagen.")
    else:
        try:
            # 1. Carga de datos
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            df = df.dropna(subset=['Estudio', 'Precio'])
            # Asegurar que la columna 'Plan' existe
            if 'Plan' not in df.columns: df['Plan'] = 'Basico'

            # 2. Identificación del estudio
            nombre_estudio = manual.upper() if manual else ""
            if not manual:
                model = genai.GenerativeModel('models/gemini-flash-latest')
                with st.spinner('IA analizando tu orden...'):
                    res = model.generate_content(["Identifica el examen. Solo el nombre.", PIL.Image.open(up_img)])
                    nombre_estudio = res.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>📋 ESTUDIO DETECTADO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # 3. Filtrado Inteligente
            keywords = [p for p in limpiar(nombre_estudio).split() if len(p) > 2]
            if not keywords: keywords = [limpiar(nombre_estudio)]
            
            res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in limpiar(x) for k in keywords))].copy()

            if not res_df.empty:
                # 4. Geolocalización
                geo = Nominatim(user_agent="biodata_premium_v1")
                u_loc = geo.geocode(u_city)
                u_lat, u_lon = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)

                kms, coords = [], []
                for i in range(len(res_df)):
                    d, c = 99.0, None
                    direc = str(res_df.iloc[i].get('Direccion', '')).strip()
                    if direc and direc.lower() != 'nan':
                        try:
                            l = geo.geocode(direc)
                            if l:
                                d = calcular_distancia(u_lat, u_lon, l.latitude, l.longitude)
                                c = [l.latitude, l.longitude]
                        except: pass
                    kms.append(d)
                    coords.append(c)

                res_df['Km'] = kms
                res_df['coords'] = coords
                res_df['Precio'] = pd.to_numeric(res_df['Precio'], errors='coerce').fillna(0)

                # --- 5. LÓGICA DE MONETIZACIÓN (RANKING) ---
                # Separamos Premium de Básicos
                premium = res_df[res_df['Plan'].str.capitalize() == 'Premium'].sort_values(by='Precio' if prio == "Precio" else 'Km')
                basico = res_df[res_df['Plan'].str.capitalize() != 'Premium'].sort_values(by='Precio' if prio == "Precio" else 'Km')
                
                # Unimos: Premium siempre van arriba
                final_res = pd.concat([premium, basico])
                mejor = final_res.iloc[0]

                # 6. Visualización de Resultados
                col_i, col_m = st.columns([1, 1.5])

                with col_i:
                    es_premium = mejor['Plan'].capitalize() == 'Premium'
                    card_style = "premium-card" if es_premium else "info-card"
                    badge = '<div class="premium-badge">⭐ CENTRO VERIFICADO</div>' if es_premium else ""
                    
                    st.markdown(f'''
                        <div class="{card_style}">
                            {badge}
                            <p style="margin:0; color:#1B5E20; font-size:0.8rem;">OPCIÓN RECOMENDADA</p>
                            <h2 style="margin:5px 0;">{mejor["Nombre"]}</h2>
                            <h1 style="color: #1B5E20; margin: 5px 0;">${int(mejor["Precio"])}</h1>
                            <p style="margin:0;">📍 Distancia: {mejor["Km"]} km</p>
                        </div>
                    ''', unsafe_allow_html=True)

                    # Botones de Acción
                    if 'Whatsapp' in mejor:
                        wa = str(mejor['Whatsapp']).split('.')[0]
                        url_c = f"https://wa.me/{wa}?text=Hola,%20vengo%20de%20BioData.%20Deseo%20cita%20para:%20{nombre_estudio}"
                        st.markdown(f'<a href="{url_c}" class="btn-whatsapp" target="_blank">💬 AGENDAR CITA</a>', unsafe_allow_html=True)

                    msg_s = f"*BioData - Info Médica*%0A• *Estudio:* {nombre_estudio}%0A• *Lugar:* {mejor['Nombre']}%0A• *Precio:* ${int(mejor['Precio'])}%0A• *Km:* {mejor['Km']}"
                    st.markdown(f'<a href="https://wa.me/?text={msg_s}" class="btn-share" target="_blank">📲 COMPARTIR RESULTADO</a>', unsafe_allow_html=True)

                with col_m:
                    mapa = folium.Map(location=[u_lat, u_lon], zoom_start=12)
                    folium.Marker([u_lat, u_lon], popup="Tu ubicación", icon=folium.Icon(color='red')).add_to(mapa)
                    for _, r in final_res.iterrows():
                        if r['coords']:
                            color = 'orange' if r['Plan'].capitalize() == 'Premium' else 'blue'
                            folium.Marker(r['coords'], popup=r['Nombre'], icon=folium.Icon(color=color)).add_to(mapa)
                    folium_static(mapa)
                
                # Tabla comparativa con iconos
                final_res['Sede'] = final_res.apply(lambda r: f"⭐ {r['Nombre']}" if r['Plan'].capitalize() == 'Premium' else r['Nombre'], axis=1)
                st.write("### 🏥 Todas las sedes encontradas:")
                st.dataframe(final_res[['Sede', 'Precio', 'Km', 'Direccion']], use_container_width=True, hide_index=True)

            else:
                st.error(f"No encontramos sedes para '{nombre_estudio}'. Intenta con un nombre más corto.")
        except Exception as e:
            st.error(f"Ocurrió un error al procesar los datos: {e}")
