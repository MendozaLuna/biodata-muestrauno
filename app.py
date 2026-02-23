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

# 3. CSS PARA ESTÉTICA BIODATA (Tu diseño favorito)
st.markdown("""
    <style>
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #FFFFFF !important; }
    
    label, p, h1, h2, h3, span { color: #000000 !important; font-weight: 800 !important; }
    
    /* Inputs en Verde BioData */
    .stTextInput div div { background-color: #1B5E20 !important; border-radius: 10px !important; }
    .stTextInput input { color: white !important; font-weight: 600 !important; }

    [data-testid="stFileUploader"] {
        background-color: #1B5E20 !important;
        padding: 20px !important;
        border-radius: 15px !important;
    }
    [data-testid="stFileUploader"] label, [data-testid="stFileUploaderIcon"] { color: white !important; }

    /* Cuadro de Información Médica */
    .med-info-box {
        background-color: #1B5E20 !important;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
        border-left: 10px solid #2E7D32;
    }
    .med-info-box h3, .med-info-box p, .med-info-box b {
        color: #FFFFFF !important;
    }

    /* Botones */
    div.stButton > button {
        background-color: #1B5E20 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        height: 3.5em !important;
        border-radius: 10px !important;
    }

    /* Tarjetas de Resultados */
    .info-card {
        border: 4px solid #1B5E20 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #F9F9F9;
        margin-bottom: 20px;
    }
    
    .premium-card {
        border: 4px solid #FFD700 !important;
        border-radius: 15px;
        padding: 20px;
        background-color: #FFFDF0;
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
uploaded_image = st.file_uploader("Sube tu orden médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 ANALIZAR Y BUSCAR RESULTADOS"):
    if not uploaded_image:
        st.warning("⚠️ Por favor, sube una foto de la orden médica.")
    else:
        try:
            # --- CARGA Y LIMPIEZA AUTOMÁTICA DEL EXCEL ---
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = df.columns.str.strip() # Limpia espacios en nombres de columnas como "Precio "
            
            if 'Nivel' not in df.columns:
                df['Nivel'] = 'Basic'
            
            # --- ANÁLISIS CON GEMINI ---
            model = genai.GenerativeModel('models/gemini-flash-latest')
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('🔍 BioData está analizando tu orden...'):
                prompt = "Analiza esta orden médica. NOMBRE: [nombre estudio] DESC: [que es] RECO: [utilidad]. Responde solo con ese formato corto."
                response = model.generate_content([prompt, img])
                raw_text = response.text
                
                nombre_estudio = "DESCONOCIDO"
                for line in raw_text.split('\n'):
                    if "NOMBRE:" in line: nombre_estudio = line.split("NOMBRE:")[1].strip().upper()

                st.markdown(f"""
                    <div class="med-info-box">
                        <h3>✅ {nombre_estudio}</h3>
                        <p>Análisis de orden médica completado con éxito.</p>
                    </div>
                """, unsafe_allow_html=True)

                # --- FILTRADO DE RESULTADOS ---
                palabras_clave = limpiar_texto(nombre_estudio).split()
                resultados = df[df['Estudio'].apply(lambda x: any(p in limpiar_texto(str(x)) for p in palabras_clave))].copy()

                if not resultados.empty:
                    # Geolocalización
                    geolocator = Nominatim(user_agent="biodata_v7")
                    u_loc = geolocator.geocode(user_city)
                    lat_i, lon_i = (u_loc.latitude, u_loc.longitude) if u_loc else (10.48, -66.90)
                    
                    def geo_calc(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            return round(geodesic((lat_i, lon_i), (loc.latitude, loc.longitude)).km, 1) if loc else 99.0
                        except: return 99.0

                    resultados['Km'] = resultados.apply(geo_calc, axis=1)
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    
                    # --- LÓGICA SAAS: SEPARACIÓN PREMIUM/BASIC ---
                    premium_df = resultados[resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio')
                    basic_df = resultados[~resultados['Nivel'].astype(str).str.contains('Premium', case=False)].sort_values(by='Precio' if prioridad == "Precio" else 'Km')
                    
                    col_info, col_map = st.columns([1, 1.5])
                    
                    with col_info:
                        # Nota de confianza
                        fecha_hoy = datetime.date.today().strftime("%d/%m/%Y")
                        st.markdown(f"""
                            <div style="background-color: #E8F5E9; padding: 10px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 1px solid #1B5E20;">
                                <span style="color: #1B5E20; font-weight: 800; font-size: 0.85rem;">
                                    ✅ Precios verificados hoy: {fecha_hoy}
                                </span>
                            </div>
                        """, unsafe_allow_html=True)

                        # 1. Centros Premium
                        if not premium_df.empty:
                            st.write("### ⭐ SOCIOS DESTACADOS")
                            for _, row in premium_df.iterrows():
                                wa = str(int(row['Whatsapp'])) if pd.notna(row['Whatsapp']) else ""
                                msg = f"Hola! Vengo de *BioData*. Deseo agendar *{nombre_estudio}* en {row['Nombre']}."
                                url = f"https://wa.me/{wa}?text={msg.replace(' ', '%20')}"
                                st.markdown(f"""
                                    <div class="premium-card">
                                        <p style="color:#B8860B; margin:0; font-size: 0.8rem;">💎 ATENCIÓN PRIORITARIA</p>
                                        <h3 style="margin:5px 0;">{row['Nombre']}</h3>
                                        <h2 style="color:#1B5E20; margin:0;">${int(row['Precio'])}</h2>
                                        <p>📍 {row['Km']} km</p>
                                        <a href="{url}" class="btn-whatsapp" target="_blank">💬 AGENDAR AHORA</a>
                                    </div>
                                """, unsafe_allow_html=True)

                        # 2. Mejor Opción Basic
                        if not basic_df.empty:
                            mejor = basic_df.iloc[0]
                            wa_m = str(int(mejor['Whatsapp'])) if pd.notna(mejor['Whatsapp']) else ""
                            msg_m = f"Hola, me interesa el precio de *{nombre_estudio}* en {mejor['Nombre']}."
                            url_m = f"https://wa.me/{wa_m}?text={msg_m.replace(' ', '%20')}"
                            st.write("### 📋 MEJOR PRECIO")
                            st.markdown(f"""
                                <div class="info-card">
                                    <h3 style="margin:0;">{mejor['Nombre']}</h3>
                                    <h2 style="color:#1B5E20; margin:10px 0;">${int(mejor['Precio'])}</h2>
                                    <p>📍 {mejor['Km']} km</p>
                                    <a href="{url_m}" class="btn-whatsapp" target="_blank">💬 CONSULTAR</a>
                                </div>
                            """, unsafe_allow_html=True)

                        # 3. Botón Compartir
                        res_comp = f"🔍 *BioData* %0A✅ *Estudio:* {nombre_estudio}%0A🏥 *Sugerido:* {resultados.iloc[0]['Nombre']}%0A💰 *Precio:* ${int(resultados.iloc[0]['Precio'])}"
                        st.markdown(f'<a href="https://wa.me/?text={res_comp}" class="btn-whatsapp" style="background-color:#34B7F1 !important;" target="_blank">📲 COMPARTIR REPORTE</a>', unsafe_allow_html=True)

                    with col_map:
                        m = folium.Map(location=[lat_i, lon_i], zoom_start=13)
                        folium.Marker([lat_i, lon_i], popup="Tu ubicación", icon=folium.Icon(color='red')).add_to(m)
                        folium_static(m)
                    
                    # --- 4. LISTADO COMPLETO DE OTRAS OPCIONES (Lo nuevo) ---
                    st.write("---")
                    st.write("### 📋 Todas las sedes que ofrecen este estudio")
                    vista_tabla = resultados[['Nombre', 'Precio', 'Km', 'Direccion', 'Redes Sociales']].copy()
                    vista_tabla = vista_tabla.sort_values(by='Precio')
                    vista_tabla.columns = ['Centro Médico', 'Precio ($)', 'Distancia (Km)', 'Dirección', 'RRSS']
                    
                    st.dataframe(
                        vista_tabla, 
                        use_container_width=True, 
                        hide_index=True
                    )

                else:
                    st.error(f"No encontramos sedes para '{nombre_estudio}'.")
        except Exception as e:
            st.error(f"Error: {e}")
