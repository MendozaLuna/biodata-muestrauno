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
import time

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
    "Pampatar26": "Salud Visual Margarita",
    "OftalmoPlus26": "Oftalmo Plus"
}

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }
    
    .brand-title { 
        color: #004D40 !important; 
        font-size: 5rem !important; 
        font-weight: 800 !important; 
        letter-spacing: -2px !important; 
        margin-bottom: 0px !important; 
        text-align: center !important; 
    }
    .brand-slogan { 
        color: #26A69A !important; 
        font-size: 1.5rem !important; 
        font-weight: 400 !important; 
        margin-top: -10px !important; 
        margin-bottom: 40px !important; 
        text-align: center !important; 
    }
    
    div.stButton > button { 
        background: linear-gradient(135deg, #26A69A 0%, #00796B 100%) !important; 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        width: 100%; 
        border-radius: 50px !important;
        border: none !important; 
        padding: 12px 24px !important;
        box-shadow: 0 4px 15px rgba(38, 166, 154, 0.3) !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        white-space: pre-line;
    }

    div.stButton > button p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    div.stButton > button:hover {
        background: linear-gradient(135deg, #00897B 0%, #00695C 100%) !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(0, 121, 107, 0.4) !important;
    }
    
    .med-info-box { 
        background: linear-gradient(135deg, #00796B 0%, #26A69A 100%) !important; 
        padding: 25px; 
        border-radius: 20px; 
        margin: 20px 0; 
    }
    .med-info-box h4, .med-info-box p { color: #FFFFFF !important; }

    .premium-card, .pro-card, .standard-card { border-radius: 25px; padding: 30px; text-align: center; }
    .premium-card { background: #FFFDF0; border: 1px solid #D4AF37 !important; }
    .premium-card h1, .premium-card h2, .premium-card p { color: #101828 !important; }

    .btn-wa { background-color: #25D366 !important; color: white !important; padding: 14px; text-align: center; border-radius: 50px; text-decoration: none; display: block; font-weight: 700; margin-top: 15px; }
    .btn-share { background-color: transparent !important; color: #00796B !important; text-align: center; text-decoration: none !important; display: block; font-weight: 600; margin-top: 10px; padding: 10px; border: 2px solid #00796B !important; border-radius: 50px; }
    
    .status-badge {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCIONES ---
@st.cache_data(show_spinner=False)
def analizar_texto_ai(texto_manual):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    res = model.generate_content(f"Define brevemente: {texto_manual}. Máximo 20 palabras.")
    return texto_manual.upper(), res.text.strip()

@st.cache_data(show_spinner=False)
def generar_copy_oferta(estudio, precio):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    prompt = f"Escribe un copy publicitario corto y persuasivo para Instagram/WhatsApp de una clínica oftalmológica. Oferta: {estudio} por solo ${precio}. Incluye emojis y un llamado a la acción claro."
    res = model.generate_content(prompt)
    return res.text

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

def calcular_distancia(la1, lo1, la2, lo2):
    try:
        R = 6371.0
        dlat, dlon = math.radians(la2-la1), math.radians(lo2-lo1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dlon/2)**2
        return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)
    except: return 99.0

def definir_estilo(row):
    p = str(row.get('Plan', 'Básico')).strip().capitalize()
    if p == "Premium": return "premium-card", "💎 ALIADO PREMIUM", "#D4AF37", 1
    if p == "Pro": return "pro-card", "✅ SEDE PRO", "#00796B", 2
    return "standard-card", "📍 SEDE BÁSICA", "#808080", 3

# --- 5. LÓGICA DE NAVEGACIÓN ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown('<h1 class="brand-title">BioData</h1>', unsafe_allow_html=True)
    st.markdown('<p class="brand-slogan">Conecta. Explora. Soluciona.</p>', unsafe_allow_html=True)
    
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
    # Esto SOLO se ejecuta si la variable NO EXISTE (la primera vez que abres la app)
    if 'u_lat' not in st.session_state: 
        st.session_state.u_lat = 10.4806
    if 'u_lon' not in st.session_state: 
        st.session_state.u_lon = -66.9036

    # 2. CREACIÓN DE VARIABLES LOCALES (Esto es lo que el buscador y el mapa necesitan leer)
    u_lat = st.session_state.u_lat
    u_lon = st.session_state.u_lon
    
    # Inicialización del estado para que la selección no borre los datos
    if 'busqueda_realizada' not in st.session_state:
        st.session_state.busqueda_realizada = False
        st.session_state.final_df = None
        st.session_state.n_est_guardado = ""
        st.session_state.m_folium_guardado = None

    if st.button("⬅️ Volver", key="back_p"): 
        st.session_state.perfil = None
        st.session_state.busqueda_realizada = False # Limpiar búsqueda al salir
        st.rerun()

    st.title("🔍 Buscador de Estudios")
    
    st.markdown("### 📍 ¿Dónde te encuentras?")
    col_btn, col_txt = st.columns([1, 2])
    
    if col_btn.button("🎯 USAR MI GPS", key="gps_btn"): 
        st.session_state.disparar_gps = True

    if st.session_state.get('disparar_gps', False):
        loc = streamlit_js_eval(data_string="navigator.geolocation.getCurrentPosition", want_output=True, key="gps_p")
        if loc and 'coords' in loc:
            st.session_state.u_lat = loc['coords']['latitude']
            st.session_state.u_lon = loc['coords']['longitude']
            st.success("✅ GPS Detectado")
            st.session_state.disparar_gps = False 

    with col_txt:
        # Aquí usamos st.session_state.u_lat para saber si ya tenemos GPS
        default_city = "Caracas" if st.session_state.u_lat == 10.4806 else "Ubicación GPS"
        u_city = st.text_input("Tu ubicación:", value=default_city, key="city_input")

    st.write("---")
    c1, c2 = st.columns(2)
    with c1: 
        prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True, key="sort_radio")
    with c2: 
        manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT...", key="exam_input")
    
    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"], key="img_uploader")
    
# BOTÓN DE BÚSQUEDA
    if st.button("🚀 BUSCAR MEJORES OPCIONES", key="main_search"):
        try:
            df = pd.read_excel("base_clinicas.xlsx")
            df.columns = [str(c).strip().capitalize() for c in df.columns]

            try:
                inv_resp = supabase.table("inventario_equipos").select("clinica, equipo, estado").order("ultima_actualizacion", desc=True).execute()
                df_inv_global = pd.DataFrame(inv_resp.data).drop_duplicates(subset=['clinica', 'equipo'])
            except:
                df_inv_global = pd.DataFrame(columns=['clinica', 'equipo', 'estado'])

            with st.spinner('Analizando solicitud...'):
                if manual: 
                    n_est, d_est = analizar_texto_ai(manual)
                elif up_img: 
                    n_est, d_est = analizar_imagen_ai(up_img.getvalue())
                else: 
                    st.warning("Escribe el examen o sube una foto.")
                    st.stop()
            
                st.session_state.n_est_guardado = n_est # Guardamos para el mensaje de WA

                if u_lat and u_lon: 
                    c_lat, c_lon = u_lat, u_lon
                else:
                    try:
                        geo = Nominatim(user_agent="biodata_v26_app")
                        loc_manual = geo.geocode(u_city)
                        c_lat, c_lon = (loc_manual.latitude, loc_manual.longitude) if loc_manual else (10.48, -66.90)
                    except: 
                        c_lat, c_lon = 10.48, -66.90
                
                # Guardar en sesión para el mapa
                st.session_state.u_lat = c_lat
                st.session_state.u_lon = c_lon

                registrar_busqueda(c_lat, c_lon, n_est)
                
                def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
                palabras = [p for p in norm(n_est).split() if len(p) > 2]
                res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()
                
                if not res_df.empty:
                    # 1. VERIFICAR SI LOS EQUIPOS ESTÁN OPERATIVOS
                    def esta_operativo(clinica_nom, est_nom):
                        if df_inv_global.empty: return True
                        match = df_inv_global[(df_inv_global['clinica'] == clinica_nom) & (df_inv_global['equipo'].apply(lambda x: x.lower() in est_nom.lower()))]
                        return match.iloc[0]['estado'] == "Operativo" if not match.empty else True
                    
                    res_df['Disponible'] = res_df.apply(lambda r: esta_operativo(r['Nombre'], n_est), axis=1)
                    res_df = res_df[res_df['Disponible'] == True].copy()

                    # 2. ACTUALIZAR UBICACIÓN CON FORMATO INTELIGENTE (Cualquier Ciudad)
                    if u_city and u_city not in ["Caracas", "Ubicación GPS"]:
                        try:
                            geo = Nominatim(user_agent="biodata_v26_app")
                            
                            # Limpiamos y preparamos la consulta
                            entrada = u_city.strip()
                            
                            # LÓGICA DE FORMATO:
                            # Si el usuario pone coma (ej: "Av. Bolivar, Valencia"), lo dejamos tal cual.
                            # Si no pone coma, le añadimos "Venezuela" para que busque en todo el país.
                            if "," in entrada:
                                query_completa = f"{entrada}, Venezuela" if "venezuela" not in entrada.lower() else entrada
                            else:
                                # Si es una sola palabra, buscamos ciudad o calle en Venezuela
                                query_completa = f"{entrada}, Venezuela"
                            
                            loc_manual = geo.geocode(query_completa)
                            
                            if loc_manual:
                                st.session_state.u_lat = loc_manual.latitude
                                st.session_state.u_lon = loc_manual.longitude
                                
                                # AJUSTE DE ZOOM DINÁMICO:
                                # Si la dirección es larga (calle), hacemos zoom. Si es corta (ciudad), zoom alejado.
                                st.session_state.zoom_mapa = 15 if "," in entrada or "av" in entrada.lower() else 12
                            else:
                                st.warning(f"No encontramos '{entrada}'. Prueba con: Calle, Ciudad")
                        except:
                            pass

                    # 3. CALCULAR DISTANCIAS USANDO EL CEREBRO (SESSION_STATE)
                    res_df['Km'] = res_df.apply(
                        lambda r: calcular_distancia(st.session_state.u_lat, st.session_state.u_lon, float(r['Latitud']), float(r['Longitud'])), 
                        axis=1
                    )

                    # 4. ORDENAMIENTO DINÁMICO
                    if prio == "Precio":
                        st.session_state.final_df = res_df.sort_values('Precio')
                    else:
                        st.session_state.final_df = res_df.sort_values('Km')
                    
                    # 5. GUARDAR ESTADO, MENSAJE Y REFRESCAR MAPA
                    st.session_state.busqueda_realizada = True
                    st.success(f"📍 Ubicación actualizada a: {u_city}")
                    
                    time.sleep(0.5)
                    st.rerun()

        except Exception as e:
            st.error(f"Error en búsqueda: {e}")

    # --- MOSTRAR RESULTADOS (Fuera del botón...) ---
   # --- MOSTRAR RESULTADOS (Fuera del botón...) ---
    if st.session_state.get('busqueda_realizada') and st.session_state.final_df is not None:
        st.write("---")
        col_i, col_m = st.columns([1, 1])

        with col_m:
            st.write("### 🗺️ Mapa de Sedes")
            
            # 1. Coordenadas desde el cerebro de la app
            lat_mapa = st.session_state.u_lat
            lon_mapa = st.session_state.u_lon
            
            # 2. Crear UN SOLO mapa
            m_folium = folium.Map(location=[lat_mapa, lon_mapa], zoom_start=12)
            
            # 3. Marcador del Usuario (Rojo)
            folium.Marker(
                [lat_mapa, lon_mapa], 
                tooltip="Tu ubicación", 
                icon=folium.Icon(color='red', icon='user', prefix='fa')
            ).add_to(m_folium)

           # 4. Dibujar clínicas (Un solo bucle para todos los marcadores)
for _, row in st.session_state.final_df.iterrows():
    if pd.notnull(row.get('Latitud')):
        p_color = 'orange' if str(row.get('Plan')) == 'Premium' else 'blue'
        
        # --- CORRECCIÓN AQUÍ: Limpiamos el precio antes de usarlo ---
        # Convertimos a número, si falla ponemos 0, y aseguramos que sea entero
        precio_limpio = int(pd.to_numeric(row.get('Precio'), errors='coerce') or 0)
        
        folium.Marker(
            [float(row['Latitud']), float(row['Longitud'])],
            tooltip=f"{row['Nombre']} - ${precio_limpio}", # <--- Usamos la variable limpia
            icon=folium.Icon(color=p_color, icon='plus', prefix='fa')
        ).add_to(m_folium)
            
            # 5. Renderizar el mapa UNA SOLA VEZ
            folium_static(m_folium, width=500, height=500)

        with col_i:
            st.write("### 🏥 Sedes Disponibles")
            
            # --- NUEVO: MENSAJE DE MEJOR PRECIO ---
            if not st.session_state.final_df.empty:
                mejor_p = int(st.session_state.final_df['Precio'].min())
                st.markdown(f"""
                    <div style="background-color: #E8F5E9; border-left: 5px solid #2E7D32; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                        <span style="color: #2E7D32; font-weight: bold;">💡 ¡Opción más económica encontrada por solo ${mejor_p}!</span>
                    </div>
                """, unsafe_allow_html=True)
            
            # 1. Definimos la regla de estilo para resaltar el precio más bajo
            def resaltar_minimo(columna_precio):
                es_minimo = columna_precio == columna_precio.min()
                return ['background-color: #C8E6C9; color: #1B5E20; font-weight: bold;' if v else '' for v in es_minimo]

            # 2. Creamos la versión visual (estilizada) del DataFrame
            df_visual = st.session_state.final_df[['Nombre', 'Precio', 'Km']].style.apply(
                resaltar_minimo, 
                subset=['Precio']
            ).format({
                "Precio": "${:.0f}", 
                "Km": "{:.1f} km"
            })

            # 3. Mostramos la tabla interactiva
            seleccion = st.dataframe(
                df_visual, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun",
                selection_mode="single-row", 
                key="tabla_interactiva"
            )
            
            # ... sigue el resto de tu código (idx = seleccion.selection.rows...)

            # Lógica para mostrar la clínica seleccionada
            idx = seleccion.selection.rows[0] if seleccion.selection.rows else 0
            mostrar = st.session_state.final_df.iloc[idx]

            # Tarjeta de presentación con colores dinámicos
            plan = str(mostrar.get('Plan', 'Básico')).strip().capitalize()
            if plan == "Premium":
                bg, brd, txt, lbl = "#FFFDF0", "#D4AF37", "#B8860B", "💎 ALIADO PREMIUM"
            elif plan == "Pro":
                bg, brd, txt, lbl = "#F5F5F5", "#C0C0C0", "#708090", "✅ SEDE PRO"
            else:
                bg, brd, txt, lbl = "#E3F2FD", "#2196F3", "#1976D2", "📍 SEDE BÁSICA"

            st.markdown(f"""
                <div style="background-color: {bg}; padding: 20px; border-radius: 15px; border: 2px solid {brd}; text-align: center; margin-bottom: 10px;">
                    <p style="color: {txt}; font-weight: 800; margin: 0; font-size: 12px; letter-spacing: 1px;">{lbl}</p>
                    <h2 style="color: #101828; margin: 5px 0; font-size: 22px;">{mostrar['Nombre']}</h2>
                    <h1 style="color: #101828; margin: 5px 0; font-size: 40px;">${int(mostrar['Precio'])}</h1>
                    <p style="color: #667085; margin: 0;">📍 A {mostrar['Km']} km de tu ubicación</p>
                </div>
            """, unsafe_allow_html=True)

            # Preparación de datos para botones
            wa_num = str(mostrar.get('Whatsapp', '584120000000')).split('.')[0]
            est_n = st.session_state.get('n_est_guardado', 'Estudio Médico')
            precio_f = int(mostrar['Precio'])
            nombre_sede = mostrar['Nombre']

            # Redacción Formal: Directo y Clínico
            # Usamos asteriscos (*) para que el estudio salga en negrita en WhatsApp
            cuerpo_mensaje = (
                f"Estimados, gusto en saludarles. Estoy interesado en realizarme el examen de *{est_n}* "
                f"en su sede de {nombre_sede}. Consulté su presupuesto de ${precio_f} a través de *BioData.* "
                f"¿Cuáles son los requisitos previos o preparación necesaria para este estudio?"
            )
            
            msg_c = urllib.parse.quote(cuerpo_mensaje)
            
            # --- MENSAJE 2: PARA EL FAMILIAR (FICHA TÉCNICA) ---
            # Creamos el link de WhatsApp simplificado para el familiar
            wa_link_directo = f"https://wa.me/{wa_num}"
            
            mensaje_familiar = (
                f"🏥 *OPCIÓN MÉDICA - BIODATA*\n\n"
                f"🔬 *Estudio:* {est_n}\n"
                f"📍 *Sede:* {nombre_sede}\n"
                f"💰 *Costo:* ${precio_f}\n\n"
                f"📱 *Contacto Directo:* {wa_link_directo}\n"
            )
            texto_sh = urllib.parse.quote(mensaje_familiar)
            
            # URL de Google Maps (Modo Ruta Directa)
            lat_dest, lon_dest = mostrar['Latitud'], mostrar['Longitud']
            lat_orig, lon_orig = st.session_state.u_lat, st.session_state.u_lon
            g_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={lat_orig},{lon_orig}&destination={lat_dest},{lon_dest}&travelmode=driving"

            html_final = f"""
            <div style="display: flex; flex-direction: column; gap: 10px; font-family: sans-serif;">
                <a href="https://wa.me/{wa_num}?text={msg_c}" target="_blank" style="text-decoration: none;">
                    <div style="background-color: #25D366; color: white !important; padding: 12px; border-radius: 50px; text-align: center; font-weight: 700; font-size: 14px;">📱 CONTACTAR POR WHATSAPP</div>
                </a>
                <a href="https://api.whatsapp.com/send?text={texto_sh}" target="_blank" style="text-decoration: none;">
                    <div style="border: 2px solid #00796B; color: #00796B !important; padding: 10px; border-radius: 50px; text-align: center; font-weight: 600; font-size: 14px;">🔗 COMPARTIR ESTA OPCIÓN</div>
                </a>
                <a href="{g_maps_url}" target="_blank" style="text-decoration: none;">
                    <div style="background-color: #4285F4; color: white !important; padding: 12px; border-radius: 50px; text-align: center; font-weight: 700; font-size: 14px;">📍 CÓMO LLEGAR (MAPS)</div>
                </a>
            </div>
            """
            import streamlit.components.v1 as components
            components.html(html_final, height=220)
            
# --- 7. CONTENIDO EMPRESA ---
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): st.session_state.perfil = None; st.rerun()
    st.title("🏥 Portal de Gestión")
    clave = st.text_input("Clave de Acceso", type="password", key="pass_e")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        
        tab_stats, tab_premium, tab_oferta, tab_inventario = st.tabs([
            "📊 Estadísticas", "💎 ANÁLISIS PREMIUM", "⚡ OFERTA RELÁMPAGO", "🛠️ GESTIÓN DE INVENTARIO"
        ])
        
        with tab_stats:
            c_f1, c_f2 = st.columns(2)
            f_ini = c_f1.date_input("Desde:", date.today() - timedelta(days=7))
            f_fin = c_f2.date_input("Hasta:", date.today())
            
            try:
                resp = supabase.table("busquedas_stats").select("*").execute()
                df_full = pd.DataFrame(resp.data)
                
                if not df_full.empty:
                    # Conversión de fechas
                    df_full['fecha_dt'] = pd.to_datetime(df_full['fecha']).dt.tz_localize(None)
                    # Filtro por rango de fecha
                    df_stats = df_full[(df_full['fecha_dt'] >= pd.Timestamp(f_ini)) & (df_full['fecha_dt'] <= pd.Timestamp(f_fin) + timedelta(days=1))].copy()
                    
                    if not df_stats.empty:
                        # --- LIMPIEZA DE DATOS ---
                        df_stats['estudio'] = df_stats['estudio'].str.strip().str.upper()
                        # Filtro para eliminar basura (registros con "NOMBRE")
                        df_stats = df_stats[~df_stats['estudio'].str.contains("NOMBRE", na=False)]
                        
                        # Mostrar Métrica
                        st.metric("Búsquedas Totales", len(df_stats))
                        
                        # Preparar datos para el Top 5
                        top_data = df_stats['estudio'].value_counts().head(5).reset_index()
                        top_data.columns = ['estudio', 'conteo']
                        
                        # Gráfico único y estilizado
                        st.subheader("📊 Top 5 Estudios Más Buscados")
                        st.altair_chart(
                            alt.Chart(top_data).mark_bar().encode(
                                x=alt.X('estudio', sort='-y', title="Estudio"),
                                y=alt.Y('conteo', title="Cantidad"),
                                color=alt.Color('estudio', legend=None)
                            ), use_container_width=True
                        )
                    else:
                        st.info("No hay búsquedas en el rango de fechas seleccionado.")
                else:
                    st.warning("La base de datos está vacía.")
                    
            except Exception as e:
                st.error(f"Error en estadísticas: {e}")
                
        with tab_premium:
            if nombre_c == "ADMIN" or "Premium" in clave:
                st.subheader("📊 Análisis de Mercado y Precios")
                try:
                    # 1. Carga de Datos
                    df_completo = pd.read_excel("base_clinicas.xlsx")
                    df_completo.columns = [str(c).strip().capitalize() for c in df_completo.columns]
                    
                    # 2. Selector de Estudios
                    todos_los_estudios = sorted(df_completo['Estudio'].unique().tolist())
                    estudios_buscados = st.multiselect(
                        "Seleccione estudios para analizar:", 
                        options=todos_los_estudios, 
                        default=[todos_los_estudios[0]] if todos_los_estudios else None,
                        key="ms_premium_select"
                    )

                    if estudios_buscados:
                        df_comp = df_completo[df_completo['Estudio'].isin(estudios_buscados)]
                        
                        # 3. Market Share
                        share = df_comp.groupby('Nombre').size().reset_index(name='Sedes')
                        share['%'] = (share['Sedes'] / share['Sedes'].sum()) * 100
                        
                        col1, col2 = st.columns([1, 1.2])
                        with col1:
                            st.write("**Sedes por Clínica**")
                            st.dataframe(share.sort_values('%', ascending=False), hide_index=True, use_container_width=True)
                        
                        with col2:
                            import plotly.express as px
                            fig = px.pie(share, values='%', names='Nombre', hole=0.4)
                            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250, showlegend=True, legend=dict(orientation="h", y=-0.2))
                            st.plotly_chart(fig, use_container_width=True)

                        # 4. Comparativa de Precios
                        st.markdown("---")
                        st.subheader("💰 Comparativa de Precios")
                        precios = df_comp['Precio'].astype(float)
                        tu_p_df = df_comp[df_comp['Nombre'].str.contains(nombre_c, case=False, na=False)]
                        
                        m1, m2, m3 = st.columns(3)
                        p_promedio = precios.mean()
                        
                        if not tu_p_df.empty:
                            tp = float(tu_p_df['Precio'].mean())
                            dif = ((tp - p_promedio) / p_promedio) * 100
                            m1.metric("Tu Precio Prom.", f"${tp:.0f}", f"{dif:+.1f}% vs Mercado", delta_color="inverse")
                        else:
                            m1.metric("Tu Precio", "N/A")
                            
                        m2.metric("Mínimo Mercado", f"${precios.min():.0f}")
                        m3.metric("Promedio General", f"${p_promedio:.0f}")

                        # --- 5. ANALISTA DE ESTRATEGIA IA ---
                        st.markdown("---")
                        with st.container():
                            st.subheader("🤖 Análisis Estratégico (BioData AI)")
                            
                            # Lógica del Consultor IA
                            n_competidores = len(share)
                            mi_share = share[share['Nombre'].str.contains(nombre_c, case=False, na=False)]['%'].sum()
                            precio_vs_promedio = ((tp - p_promedio) / p_promedio) * 100 if not tu_p_df.empty else 0
                            
                            # Construcción del diagnóstico
                            if mi_share > (100 / n_competidores):
                                mkt_status = "Líder de Presencia"
                                mkt_desc = "Tienes una cobertura superior al promedio."
                            else:
                                mkt_status = "Retador en Crecimiento"
                                mkt_desc = "Tu presencia en sedes es limitada frente a la competencia."

                            if precio_vs_promedio > 5:
                                px_status = "Premium / Alto"
                                px_desc = "Tus precios están notablemente por encima del mercado. Asegúrate de resaltar valores agregados."
                            elif precio_vs_promedio < -5:
                                px_status = "Competitivo / Agresivo"
                                px_desc = "Tienes una ventaja de precio clara para captar volumen."
                            else:
                                px_status = "Equilibrado"
                                px_desc = "Estás alineado con el promedio del mercado."

                            # Mostrar el análisis en un cuadro llamativo
                            st.info(f"""
                            **Diagnóstico de Mercado:** {mkt_status} ({mi_share:.1f}% de cuota). {mkt_desc}
                            
                            **Estrategia de Precios:** {px_status}. {px_desc}
                            
                            **💡 Recomendación:** {"Considera una campaña de fidelización si tu precio es alto," if precio_vs_promedio > 0 else "Aprovecha tu precio bajo para pautar en redes sociales,"} enfocada en los estudios de: {", ".join(estudios_buscados[:2])}.
                            """)

                        with st.expander("🔍 Ver detalle de precios por sede"):
                            st.dataframe(df_comp[['Nombre', 'Precio']].sort_values('Precio'), use_container_width=True, hide_index=True)
                    else:
                        st.info("👆 Selecciona al menos un estudio para ver el análisis.")

                except Exception as e:
                    st.error(f"Error en el análisis: {e}")

                # 5. Mapa de Calor (Alineado con el try de arriba)
                st.markdown("---")
                st.subheader("📍 Mapa de Calor de Demanda")
                try:
                    resp_map = supabase.table("busquedas_stats").select("lat, lon").execute()
                    pts = pd.DataFrame(resp_map.data).dropna().values.tolist()
                    m_p = folium.Map(location=[10.48, -66.90], zoom_start=11)
                    if pts: 
                        from folium.plugins import HeatMap
                        import folium
                        from streamlit_folium import folium_static

                        # 1. Crear el mapa base
                        m_p = folium.Map(location=[10.48, -66.90], zoom_start=12)
                        
                        # 2. Agregar el Mapa de Calor (Demanda)
                        HeatMap(pts).add_to(m_p)

                        # 3. AGREGAR EL ICONO DE TU CLÍNICA (Oferta)
                        try:
                            # Buscamos las coordenadas de la clínica en el dataframe original
                            mi_sede = df_completo[df_completo['Nombre'].str.contains(nombre_c, case=False, na=False)].iloc[0]
                            lat_c = mi_sede['Lat']
                            lon_c = mi_sede['Lon']
                            
                            # 3. AGREGAR EL PIN DE TU CLÍNICA (Oferta)
                            mi_sede = df_completo[df_completo['Nombre'].str.contains(nombre_c, case=False, na=False)].iloc[0]
                            lat_c = mi_sede['Lat']
                            lon_c = mi_sede['Lon']
                            
                            # Usamos DivIcon para renderizar el emoji directamente
                            from folium.features import DivIcon
                            
                            folium.Marker(
                                [lat_c, lon_c],
                                popup=f"<b>{nombre_c}</b>",
                                icon=DivIcon(
                                    icon_size=(30,30),
                                    icon_anchor=(15,30),
                                    html=f'<div style="font-size: 24pt;">📍</div>',
                                )
                            ).add_to(m_p)
                        except Exception as e:
                            # Si falla, el mapa sigue pero sin el pin
                            pass
                            
                        # 4. Mostrar el mapa
                        folium_static(m_p)

                        # --- ANALISTA DE MAPA IA CON INTERPRETACIÓN DE COLORES ---
                        st.markdown("---")
                        with st.container():
                            st.subheader("🤖 Interpretación Estratégica del Mapa (BioData AI)")
                            
                            n_puntos = len(pts)
                            
                            if n_puntos > 0:
                                # Cuadro explicativo de la simbología del calor
                                st.write("### 🌡️ ¿Cómo leer este mapa de demanda?")
                                
                                col_azul, col_amarillo, col_rojo = st.columns(3)
                                
                                with col_azul:
                                    st.markdown("<p style='color: #0000FF; font-weight: bold;'>🔵 Zonas Azules</p>", unsafe_allow_html=True)
                                    st.caption("Interés Inicial: Representan consultas aisladas. Son zonas de 'exploración' donde la marca aún no es fuerte.")
                                
                                with col_amarillo:
                                    st.markdown("<p style='color: #FFD700; font-weight: bold;'>🟡 Zonas Amarillas</p>", unsafe_allow_html=True)
                                    st.caption("Demanda Activa: Existe una concentración moderada. Aquí es donde la competencia por el paciente es más fuerte.")
                                
                                with col_rojo:
                                    st.markdown("<p style='color: #FF0000; font-weight: bold;'>🔴 Zonas Rojas</p>", unsafe_allow_html=True)
                                    st.caption("Epicentro de Demanda: Saturación de búsquedas. Indica una necesidad crítica de servicios de salud en este punto exacto.")

                                # Diagnóstico Final de la IA
                                st.info(f"""
                                **Análisis de Cobertura:** El mapa muestra que tu demanda actual tiene **{n_puntos} focos de calor**. 
                                
                                📍 **Conclusión BioData:** Las manchas **Rojas** indican que hay una fuga de pacientes potenciales que no encuentran sede cercana. Si estas manchas están lejos de tu clínica {nombre_c}, estás perdiendo el mercado frente a laboratorios locales. 
                                
                                🚀 **Acción Sugerida:** Desplegar publicidad dirigida (Geofencing) específicamente en las zonas **Amarillas** para evitar que se desplacen hacia los competidores del centro.
                                """)
                            else:
                                st.warning("No hay suficientes datos de GPS para generar la interpretación de colores hoy.")
                    else:
                        st.info("No hay datos suficientes para el mapa de calor.")
                except: 
                    st.info("Cargando visor de mapas...")
            
            else:
                # Este else está ahora perfectamente alineado con: if nombre_c == "ADMIN"...
                st.error("🔒 Este contenido es exclusivo para el Plan PREMIUM.")
                
        with tab_oferta:
            st.subheader("⚡ Crear Oferta Relámpago")
            if nombre_c == "ADMIN" or "Pro" in clave or "Premium" in clave:
                c1, c2 = st.columns(2)
                opciones = ["OCT de Mácula", "Campimetría", "Topografía", "Otro..."]
                sel_temp = c1.selectbox("Estudio:", opciones, key="sel_estudio_oferta")
                estudio_final = c1.text_input("Escriba el nombre:") if sel_temp == "Otro..." else sel_temp
                precio_of = c2.number_input("Precio ($):", min_value=1, value=50)
                
                if st.button("🪄 GENERAR CON IA"):
                    with st.spinner("Generando copy..."):
                        st.info(generar_copy_oferta(estudio_final, precio_of))
            else: st.warning("🔒 Requiere Plan PRO o PREMIUM.")

        with tab_inventario:
            st.subheader(f"🛠️ Gestión de Inventario - {nombre_c}")
            lista_equipos = ["OCT", "Retinógrafo", "Campímetro", "Ecógrafo Ocular", "Láser YAG", "Topógrafo"]
            
            with st.expander("Actualizar Estado de Equipo"):
                ce1, ce2 = st.columns(2)
                eq_sel = ce1.selectbox("Equipo:", lista_equipos, key="eq_inv")
                est_sel = ce2.radio("Estatus:", ["Operativo", "En Mantenimiento"], horizontal=True, key="st_inv")
                if st.button("Guardar Cambios", use_container_width=True):
                    try:
                        supabase.table("inventario_equipos").insert({
                            "clinica": nombre_c, "equipo": eq_sel, "estado": est_sel, "ultima_actualizacion": datetime.now().isoformat()
                        }).execute()
                        st.success("✅ Actualizado."); time.sleep(1); st.rerun()
                    except: st.error("Error al guardar.")

            st.write("---")
            try:
                res_inv = supabase.table("inventario_equipos").select("*").eq("clinica", nombre_c).order("ultima_actualizacion", desc=True).execute()
                if res_inv.data:
                    df_i = pd.DataFrame(res_inv.data).drop_duplicates(subset=['equipo'])
                    for _, r in df_i.iterrows():
                        colr = "🟢" if r['estado'] == "Operativo" else "🔴"
                        st.info(f"{colr} **{r['equipo']}**: {r['estado']}")
            except: pass

# --- 8. PIE DE PÁGINA ---
st.markdown("---")
with st.form("buzon_final", clear_on_submit=True):
    st.subheader("📩 Buzón de Sugerencias")
    nombre_b = st.text_input("Nombre (Opcional)")
    asunto_b = st.selectbox("Asunto:", ["Nueva Sede", "Mejora App", "Reportar Error", "Otro"])
    mensaje_b = st.text_area("Tu comentario:")
    if st.form_submit_button("Enviar a BioData"):
        if mensaje_b: 
            st.success("✅ Recibido.")
        else: 
            st.warning("Escribe un mensaje.")

st.markdown("<p style='text-align: center; color: grey; font-size: 12px;'>BioData 2026 - Conecta. Explora. Soluciona.</p>", unsafe_allow_html=True)
