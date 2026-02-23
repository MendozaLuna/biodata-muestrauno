import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import unicodedata
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

# 3. CSS PARA ESTÉTICA UNIFICADA (Tu diseño favorito)
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }

    [data-testid="stFileUploader"] {
        background-color: #1B5E20 !important;
        padding: 20px !important;
        border-radius: 15px !important;
    }
    [data-testid="stFileUploader"] label, [data-testid="stFileUploaderIcon"] { color: white !important; }

    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }
    .med-info-box h3, .med-info-box p, .med-info-box b {
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }
    .med-info-box h3 { font-weight: 900 !important; margin-top: 0; }

    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
        border-radius: 10px !important;
    }

    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
        margin-bottom: 20px;
    }
    
    .btn-whatsapp {
        background-color: #25D366 !important;
        color: #FFFFFF !important;
        padding: 15px;
        text-align: center;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        font-weight: 900;
        font-size: 1.1rem;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def limpiar_texto(t):
    if not isinstance(t, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower().strip())
                  if unicodedata.category(c) != 'Mn')

# 4. INTERFAZ PRINCIPAL
st.title("🔍 BioData")
user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Caracas, Venezuela")
prioridad = st.radio("Prioridad de búsqueda:", ("Precio", "Ubicación"), horizontal=True)
uploaded_image = st.file_uploader("Opción para subir la orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, sube una foto de la orden médica.")
    else:
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip().str.capitalize()
            
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('🔍 BioData está analizando tu orden médica...'):
                prompt = "Analiza esta orden médica. NOMBRE: [nombre estudio] DESC: [que es] RECO: [utilidad]. Responde solo con ese formato."
                response = model.generate_content([prompt, img])
                raw_text = response.text
                
                nombre_estudio, desc_estudio, reco_estudio = "DESCONOCIDO", "", ""
                for line in raw_text.split('\n'):
                    if "NOMBRE:" in line: nombre_estudio = line.split("NOMBRE:")[1].strip().upper()
                    if "DESC:" in line: desc_estudio = line.split("DESC:")[1].strip()
                    if "RECO:" in line: reco_estudio = line.split("RECO:")[1].strip()

                st.markdown(f"""
                    <div class="med-info-box">
                        <h3>✅ {nombre_estudio}</h3>
                        <p><b>¿Qué es?</b> {desc_estudio}</p>
                        <p><b>Utilidad Médica:</b> {reco_estudio}</p>
                    </div>
                """, unsafe_allow_html=True)

                # Filtrado mejorado para evitar el error de "No se encontraron sedes"
                if nombre_estudio == "DESCONOCIDO":
                    st.error("❌ No pudimos leer el estudio. Intenta con una foto más clara.")
                else:
                    palabras_clave = limpiar_texto(nombre_estudio).split()
                    resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

                    if not resultados.empty:
                        geolocator = Nominatim(user_agent="biodata_v6")
                        u_loc = geolocator.geocode(user_city)
                        lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                        
                        m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                        
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
                        
                        # --- LÓGICA PREMIUM CORREGIDA (Línea 183 aprox) ---
                        if 'Nivel' not in resultados.columns:
                            resultados['Nivel'] = 'Basic'

                        premium_df = resultados[resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                        basic_df = resultados[~resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                        
                        col_info, col_map = st.columns([1, 1.5])
                        
                        with col_info:
                            # 1. MOSTRAR PREMIUM
                            if not premium_df.empty:
                                st.write("### ⭐ CENTROS DESTACADOS")
                                for _, row in premium_df.iterrows():
                                    tel_p = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                                    st.markdown(f"""
                                        <div class="info-card" style="border: 4px solid #FFD700 !important; background-color: #FFFDF0 !important;">
                                            <p style='margin:0; color:#B8860B;'>CENTRO VERIFICADO</p>
                                            <h2 style='margin:0;'>{row['Nombre']}</h2>
                                            <h1 style='color: #1B5E20; margin: 10px 0;'>${int(row['Precio'])}</h1>
                                            <p>📍 Distancia: {row['Km']} km</p>
                                        </div>
                                    """, unsafe_allow_html=True)
                                    if tel_p:
                                        st.markdown(f'<a href="https://wa.me/{tel_p}" class="btn-whatsapp" target="_blank">💬 AGENDAR PRIORITARIO</a>', unsafe_allow_html=True)

                            # 2. MOSTRAR RECOMENDADO
                            if not basic_df.empty:
                                mejor = basic_df.iloc[0]
                                st.write("### 📋 OPCIÓN RECOMENDADA")
                                st.markdown(f"""
                                    <div class="info-card">
                                        <p style='margin:0; color:#1B5E20;'>MEJOR RESULTADO</p>
                                        <h2 style='margin:0;'>{mejor['Nombre']}</h2>
                                        <h1 style='color: #1B5E20; margin: 10px 0;'>${int(mejor['Precio'])}</h1>
                                        <p>📍 Distancia: {mejor['Km']} km</p>
                                    </div>
                                """, unsafe_allow_html=True)
                                
                                tel_m = str(int(mejor['Whatsapp'])) if pd.notna(mejor['Whatsapp']) else ""
                                if tel_m:
                                    st.markdown(f'<a href="https://wa.me/{tel_m}" class="btn-whatsapp" target="_blank">💬 CONTACTAR CLÍNICA</a>', unsafe_allow_html=True)

                            # 3. COMPARTIR
                            msg = f"*BioData* %0A✅ {nombre_estudio} %0A🏥 {resultados.iloc[0]['Nombre']} %0A💰 ${int(resultados.iloc[0]['Precio'])}"
                            st.markdown(f'<a href="
