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
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# 3. CSS PARA ESTÉTICA BIODATA
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }
    [data-testid="stFileUploader"] { background-color: #1B5E20 !important; padding: 20px !important; border-radius: 15px !important; }
    .med-info-box { background-color: #1B5E20 !important; padding: 25px; border-radius: 15px; margin: 20px 0; }
    .med-info-box h3, .med-info-box p { color: #FFFFFF !important; }
    div.stButton > button { background-color: #1B5E20 !important; color: #FFFFFF !important; font-weight: 900 !important; width: 100%; border-radius: 10px !important; }
    .info-card { border: 4px solid #1B5E20 !important; border-radius: 15px; padding: 20px; background-color: #F9F9F9; margin-bottom: 20px; }
    .premium-card { border: 4px solid #FFD700 !important; border-radius: 15px; padding: 20px; background-color: #FFFDF0; margin-bottom: 20px; }
    .btn-whatsapp { background-color: #25D366 !important; color: #FFFFFF !important; padding: 12px; text-align: center; border-radius: 10px; text-decoration: none; display: block; font-weight: 900; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")

c1, c2 = st.columns(2)
with c1: prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
with c2: busqueda_manual = st.text_input("⌨️ Búsqueda manual:", placeholder="Ej: Oct, Eco...")

uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR"):
    if not uploaded_image and not busqueda_manual:
        st.warning("⚠️ Sube una imagen o escribe el nombre del estudio.")
    else:
        try:
            # --- CARGA Y LIMPIEZA DE COLUMNAS ---
            dict_hojas = pd.read_excel("base_clinicas.xlsx", sheet_name=None)
            df = pd.concat(dict_hojas.values(), ignore_index=True)
            
            # ELIMINAR ESPACIOS EN BLANCO DE LOS NOMBRES DE COLUMNAS (Crucial para el error)
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'Nivel' not in df.columns: df['Nivel'] = 'Basic'
            
            # --- MODELO GEMINI FLASH LATEST ---
            nombre_estudio = ""
            if busqueda_manual:
                nombre_estudio = busqueda_manual.upper()
            else:
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                with st.spinner('BioData analizando...'):
                    response = model.generate_content(["Identifica el estudio. Responde SOLO el nombre corto.", img])
                    nombre_estudio = response.text.strip().upper()

            st.markdown(f'<div class="med-info-box"><h3>✅ ESTUDIO: {nombre_estudio}</h3></div>', unsafe_allow_html=True)

            # --- FILTRADO ---
            palabras = [p for p in limpiar_texto(nombre_estudio).split() if len(p) > 2]
            resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

            if not resultados.empty:
                # --- GEOLOCALIZACIÓN MANUAL (EVITA EL ERROR DE LIST/TUPLE) ---
                geolocator = Nominatim(user_agent="biodata_final_shield")
                
                # Obtener punto usuario con respaldo
                u_res = geolocator.geocode(user_city)
                punto_usuario = (u_res.latitude, u_res.longitude) if u_res else (10.48, -66.90)

                kms = []
                coords_mapa = []

                for index, row in resultados.iterrows():
                    distancia = 99.0
                    coordenada = None
                    
                    # Intentamos geocodificar la dirección de la fila
                    direccion_sucursal = str(row.get('Direccion', '')).strip()
                    
                    if direccion_sucursal and direccion_sucursal.lower() != 'nan':
                        try:
                            loc_sucursal = geolocator.geocode(direccion_sucursal)
                            if loc_sucursal:
                                punto_sucursal = (loc_sucursal.latitude, loc_sucursal.longitude)
                                # Aquí es donde fallaba: validamos que ambos puntos sean tuplas reales
                                if isinstance(punto_usuario, tuple) and isinstance(punto_sucursal, tuple):
                                    distancia = round(geodesic(punto_usuario, punto_sucursal).km, 1)
                                    coordenada = punto_sucursal
                        except:
                            pass
                    
                    kms.append(distancia)
                    coords_mapa.append(coordenada)

                resultados['Km'] = kms
                resultados['coords'] = coords_mapa
                
                # Limpiar columna Precio (quitar el espacio si existe)
                col_precio = 'Precio' if 'Precio' in resultados.columns else 'Precio '
                resultados['Precio_Num'] = pd.to_numeric(resultados[col_precio], errors='coerce').fillna(0)
                
                # SaaS Separación
                premium = resultados[resultados['Nivel'].str.contains('Premium', case=False, na=False)].sort_values('Precio_Num')
                basic = resultados[~resultados['Nivel'].str.contains('Premium', case=False, na=False)].sort_values('Precio_Num' if prioridad == "Precio" else 'Km')
                
                col_info, col_map = st.columns([1, 1.5])
                
                with col_info:
                    st.info(f"📅 Verificado: {datetime.date.today().strftime('%d/%m/%Y')}")
                    for _, r in premium.iterrows():
                        wa = str(r.get('Whatsapp', '')).replace('.0', '')
                        url = f"https://wa.me/{wa}?text=Hola!%20Deseo%20agendar%20{nombre_estudio}"
                        st.markdown(f'<div class="premium-card"><b>💎 PREMIUM</b><h3>{r["Nombre"]}</h3><h2>${int(r["Precio_Num"])}</h2><p>📍 {r["Km"]} km</p><a href="{url}" class="btn-whatsapp" target="_blank">💬 AGENDAR</a></div>', unsafe_allow_html=True)

                    if not basic.empty:
                        m = basic.iloc[0]
                        wa_m = str(m.get('Whatsapp', '')).replace('.0', '')
                        url_m = f"https://wa.me/{wa_m}?text=Info%20sobre%20{nombre_estudio}"
                        st.markdown(f'<div class="info-card"><h3>{m["Nombre"]}</h3><h2 style="color:#1B5E20;">${int(m["Precio_Num"])}</h2><p>📍 {m["Km"]} km</p><a href="{url_m}" class="btn-whatsapp" target="_blank">💬 CONSULTAR</a></div>', unsafe_allow_html=True)

                with col_map:
                    mapa = folium.Map(location=punto_usuario, zoom_start=12)
                    folium.Marker(punto_usuario, popup="Tú", icon=folium.Icon(color='red')).add_to(mapa)
                    for _, r in resultados.iterrows():
                        if r['coords']:
                            folium.Marker(r['coords'], popup=f"{r['Nombre']}").add_to(mapa)
                    folium_static(mapa)
                
                st.write("### 📋 Comparativa Completa")
                st.dataframe(resultados[['Nombre', col_precio, 'Km', 'Direccion']], use_container_width=True, hide_index=True)
            else:
                st.error("No se encontraron sedes.")
        except Exception as e:
            st.error(f"Error de sistema: {e}")
