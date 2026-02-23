import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura 'GOOGLE_API_KEY' en los Secrets.")
    st.stop()

st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

# --- 2. CSS (Tu diseño favorito corregido) ---
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    .med-info-box h3, .med-info-box p { color: white !important; }

    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
        margin-bottom: 20px;
        color: #000000 !important; /* Fuerza visibilidad */
    }
    .info-card h1, .info-card h2, .info-card p { color: #000000 !important; margin: 5px 0; }
    
    .btn-whatsapp {
        background-color: #25D366 !important;
        color: white !important;
        padding: 12px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip()) if unicodedata.category(c) != 'Mn')

# --- 3. INTERFAZ ---
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación:", "Caracas, Venezuela")
prioridad = st.radio("Prioridad:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Sube orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Sube una foto de la orden.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('BioData analizando...'):
                prompt = "Analiza la orden. NOMBRE: [estudio] DESC: [que es] RECO: [utilidad]. Responde solo con ese formato."
                response = model.generate_content([prompt, img])
                raw = response.text
                
                nombre_e = "DESCONOCIDO"
                desc_e = ""
                for line in raw.split('\n'):
                    if "NOMBRE:" in line: nombre_e = line.split("NOMBRE:")[1].strip().upper()
                    if "DESC:" in line: desc_e = line.split("DESC:")[1].strip()

                st.markdown(f'<div class="med-info-box"><h3>✅ {nombre_e}</h3><p>{desc_e}</p></div>', unsafe_allow_html=True)

                palabras = limpiar_texto(nombre_e).split()
                resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras))].copy()

                if not resultados.empty:
                    geolocator = Nominatim(user_agent="biodata_fix")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    m = folium.Map(location=[lat_i, lon_i], zoom_start=12)
                    
                    def geo_calc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc:
                                folium.Marker([loc.latitude, loc.longitude], popup=row['Nombre']).add_to(m)
                                return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return 99.0

                    resultados['Km'] = resultados.apply(geo_calc, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    
                    # --- LÓGICA PREMIUM Y BASIC ---
                    if 'Nivel' not in resultados.columns: resultados['Nivel'] = 'Basic'
                    
                    premium_df = resultados[resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                    basic_df = resultados[~resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                    
                    # --- VISUALIZACIÓN (Indentación corregida) ---
                    col_info, col_map = st.columns([1, 1.5])
                    
                    with col_info:
                        # 1. Premium
                        if not premium_df.empty:
                            st.write("### ⭐ DESTACADOS")
                            for _, row in premium_df.iterrows():
                                tel = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                                st.markdown(f"""
                                    <div class="info-card" style="border-color:#FFD700 !important; background-color:#FFFDF0 !important;">
                                        <p style="color:#B8860B; margin:0;">SOCIO PREMIUM</p>
                                        <h2>{row['Nombre']}</h2>
                                        <h1>${int(row['Precio'])}</h1>
                                        <p>📍 {row['Km']} km</p>
                                        <a href="https://wa.me/{tel}" class="btn-whatsapp" target="_blank">💬 AGENDAR PRIORITARIO</a>
                                    </div>
                                """, unsafe_allow_html=True)

                        # 2. Mejor Opción (Basic)
                        if not basic_df.empty:
                            mejor = basic_df.iloc[0]
                            st.write("### 📋 RECOMENDADO")
                            tel_m = str(int(mejor['Whatsapp'])) if pd.notna(mejor['Whatsapp']) else ""
                            st.markdown(f"""
                                <div class="info-card">
                                    <p style="color:#1B5E20; margin:0;">MEJOR PRECIO</p>
                                    <h2>{mejor['Nombre']}</h2>
                                    <h1>${int(mejor['Precio'])}</h1>
                                    <p>📍 {mejor['Km']} km</p>
                                    <a href="https://wa.me/{tel_m}" class="btn-whatsapp" target="_blank">💬 CONTACTAR AHORA</a>
                                </div>
                            """, unsafe_allow_html=True)

                        # 3. Compartir
                        st.markdown(f'<a href="https://wa.me/?text=Resultado" class="btn-whatsapp" style="background-color:#34B7F1 !important;" target="_blank">📲 COMPARTIR</a>', unsafe_allow_html=True)

                    with col_map:
                        folium_static(m)

                    # --- SECCIÓN OTRAS OPCIONES ---
                    st.write("### 📋 OTRAS OPCIONES")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']].sort_values(by='Precio'), use_container_width=True)
                else:
                    st.error("No se encontraron sedes para este estudio.")
        except Exception as e:
            st.error(f"Error crítico: {e}")
