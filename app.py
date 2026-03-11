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
from streamlit_js_eval import get_geolocation # IMPORTANTE: Añadir esta línea
from fpdf import FPDF

@st.cache_data(show_spinner="Consultando a la IA de BioData...")
def obtener_concepto_estudio(nombre_estudio):
    try:
        # Forzamos la configuración con la llave que ya confirmamos que tienes
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Le pedimos algo muy simple para evitar bloqueos de seguridad
        prompt = f"Define brevemente el examen medico {nombre_estudio}. Maximo 15 palabras."
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text
        return "Información técnica disponible en la clínica."

    except Exception as e:
        # ESTO IMPRIMIRÁ EL ERROR REAL EN TUS LOGS AHORA MISMO
        print(f"--- ERROR CRÍTICO GEMINI ---: {str(e)}")
        
        # Diccionario de respaldo por si la IA falla (Plan B)
        respaldos = {
            "oftalmolaser": "Estudio especializado para evaluar la salud ocular y corrección visual.",
            "ecografia": "Prueba de diagnóstico por imagen que utiliza ondas sonoras.",
            "laboratorio": "Análisis clínico de muestras para evaluar el estado de salud general."
        }
        # Si el estudio está en el respaldo, lo usamos; si no, damos un mensaje genérico
        return respaldos.get(nombre_estudio.lower(), "Detalles de preparación y concepto disponibles al agendar su cita.")

    except Exception as e:
        # ESTO ES LO MÁS IMPORTANTE: 
        # El error real aparecerá en letras ROJAS en tu barra lateral para que lo veas.
        st.sidebar.error(f"Error técnico IA: {str(e)}")
        return "Consulte los detalles de preparación al agendar su cita."

def generar_pdf_presupuesto(carrito, total_general):
    # Creamos la instancia del PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado principal
    pdf.set_font("helvetica", 'B', 20)
    pdf.set_text_color(0, 77, 64) # Color verde institucional
    pdf.cell(0, 15, "BIO DATA - PRESUPUESTO MÉDICO", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Agrupamos por sede para el documento
    sedes = {}
    for item in carrito:
        sede = item.get('sede', 'Clínica por definir')
        if sede not in sedes: sedes[sede] = []
        sedes[sede].append(item)
    
    # Cuerpo del Presupuesto
    for sede, estudios in sedes.items():
        # Título de la Clínica
        pdf.set_font("helvetica", 'B', 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, f"Sede: {sede}", new_x="LMARGIN", new_y="NEXT")
        
        # Lista de estudios de esa clínica
        pdf.set_font("helvetica", size=11)
        subtotal_sede = 0
        for est in estudios:
            # Limpiamos acentos para evitar errores de codificación
            nom_est = est['estudio'].replace('í', 'i').replace('á', 'a').replace('é', 'e').replace('ó', 'o').replace('ú', 'u')
            pdf.cell(140, 8, f"  - {nom_est}", border=0)
            pdf.cell(50, 8, f"${est['precio']}", border=0, align='R', new_x="LMARGIN", new_y="NEXT")
            subtotal_sede += est['precio']
        
        # Subtotal por sede
        pdf.set_font("helvetica", 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, f"Subtotal en esta sede: ${subtotal_sede:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    # Línea divisoria y Total Final
    pdf.set_draw_color(0, 77, 64)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font("helvetica", 'B', 16)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, f"TOTAL ESTIMADO: ${total_general:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    # Nota legal al pie
    pdf.ln(20)
    pdf.set_font("helvetica", size=9)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 5, "Este documento es un presupuesto informativo generado por BioData. Los precios y disponibilidad estan sujetos a cambios directamente en la clinica seleccionada.", align='C')
    
    # fpdf2 devuelve los bytes directamente con .output()
    return pdf.output()

# --- 1. INICIALIZACIÓN DEL CARRITO (LÓGICA PURA) ---
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

def agregar_al_carrito(nombre_estudio, precio_valor, sede):
    # Verifica si el estudio ya está en el carrito para no duplicar
    if not any(item['estudio'] == nombre_estudio for item in st.session_state.carrito):
        st.session_state.carrito.append({
            'estudio': nombre_estudio, 
            'precio': precio_valor,
            'sede': sede    
        })
        return True
    return False
        
# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ La clave GOOGLE_API_KEY no está configurada en los Secrets.")
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
    st.error("⚠️ Error: Faltan las llaves en los Secrets.")
    st.stop()

# --- 2. DICCIONARIO DE ACCESOS ---
ACCESOS_CLINICAS = {
    "AdminBio2026": "ADMIN",
    "ClinisacPremium26": "Clinisac",
    "PampatarPremium26": "Salud Visual Margarita",
    "OftalmoPlus26": "Oftalmo Plus"
}

# --- 3. DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

loc = get_geolocation()

if loc:
    # Si el usuario acepta, guardamos las coordenadas reales
    st.session_state.u_lat = loc['coords']['latitude']
    st.session_state.u_lon = loc['coords']['longitude']
else:
    # Si no acepta o aún no carga, usamos una ubicación por defecto (Ej: Caracas)
    # Esto evita que la app dé error mientras el usuario decide si dar permiso
    if 'u_lat' not in st.session_state:
        st.session_state.u_lat = 10.4806
        st.session_state.u_lon = -66.9036
        
st.markdown("""
<style>
    /* 1. Importar fuente */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    
    /* 2. Ocultar header, footer y eliminar la línea negra superior */
    [data-testid="stHeader"], header, #MainMenu, footer { 
        visibility: hidden; 
        height: 0px; 
    }
    
    /* 3. Eliminar espacios residuales arriba */
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }

    /* 4. Estilo del Título BioData */
    .brand-title {
        color: #004D40 !important;
        font-size: 5rem !important;
        font-weight: 800 !important;
        letter-spacing: -2px !important;
        margin-bottom: 0px !important;
        text-align: center !important;
        font-family: 'Inter', sans-serif;
        line-height: 1;
        padding-top: 20px;
    }
    .brand-slogan { 
        color: #000000 !important; /* Aquí cambiamos a negro */
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
    
    # 1. INICIALIZACIÓN DE ESTADO (Crucial para evitar errores de "KeyError")
    if 'u_lat' not in st.session_state:
        st.session_state.u_lat, st.session_state.u_lon = 10.4806, -66.9036
    if 'busqueda_realizada' not in st.session_state:
        st.session_state.busqueda_realizada = False
    if 'sede_seleccionada' not in st.session_state:
        st.session_state.sede_seleccionada = None

    st.title("🔍 Buscador de Estudios")

    # Aviso visual para abrir el carrito en móviles
    if st.session_state.carrito:
        st.info("💡 Tienes estudios en tu presupuesto. Toca la flecha (>) arriba a la izquierda para verlos.")
        if st.button("🛒 VER MI PRESUPUESTO AHORA"):
            st.sidebar.markdown("### 🛒 Aquí está tu lista") # Esto intenta forzar el foco a la sidebar

    if st.button("⬅️ Volver al Inicio", key="back_p"): 
        st.session_state.perfil = None
        st.session_state.busqueda_realizada = False
        st.rerun()

    # --- 2. UBICACIÓN ---
    st.markdown("### 📍 ¿Dónde te encuentras?")
    
    # Botón de GPS real
    loc = get_geolocation(component_key="gps_manual_definitivo")
    if loc:
        st.session_state.u_lat = loc['coords']['latitude']
        st.session_state.u_lon = loc['coords']['longitude']
        st.success(f"✅ GPS Activo")
    
    default_city = "Caracas" if st.session_state.u_lat == 10.4806 else "Ubicación GPS"
    u_city = st.text_input("Tu ubicación (Ciudad o Zona):", value=default_city, key="city_input")

    st.write("---")
    
    # --- 3. FILTROS DE BÚSQUEDA ---
    c1, c2 = st.columns(2)
    with c1: 
        prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True, key="sort_radio")
    with c2: 
        manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Resonancia...", key="exam_input")
    
    up_img = st.file_uploader("O sube foto de la orden", type=["jpg", "jpeg", "png"])

    # --- 4. LÓGICA DE BÚSQUEDA ---
    if st.button("🚀 BUSCAR MEJORES OPCIONES", key="main_search"):
        try:
            with st.spinner('Analizando solicitud...'):
                # Simulación de carga de datos y lógica AI
                df = pd.read_excel("base_clinicas.xlsx")
                df.columns = [str(c).strip().capitalize() for c in df.columns]
                
                # Identificar estudio
                if manual: n_est, d_est = analizar_texto_ai(manual)
                elif up_img: n_est, d_est = analizar_imagen_ai(up_img.getvalue())
                else:
                    st.warning("⚠️ Ingresa un examen."); st.stop()

                # Normalización y filtrado
                def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
                palabras = [p for p in norm(n_est).split() if len(p) > 2]
                res_df = df[df['Estudio'].astype(str).apply(lambda x: any(k in norm(x) for k in palabras))].copy()

                if not res_df.empty:
                    # Cálculo de distancia
                    res_df['Km'] = res_df.apply(lambda r: calcular_distancia(st.session_state.u_lat, st.session_state.u_lon, float(r['Latitud']), float(r['Longitud'])), axis=1)
                    
                    # Ordenamiento
                    col_orden = 'Precio' if prio == "Precio" else 'Km'
                    st.session_state.final_df = res_df.sort_values(col_orden)
                    st.session_state.estudio_buscado = n_est
                    st.session_state.busqueda_realizada = True
                    st.session_state.sede_seleccionada = None # Resetear seleccion anterior
                    st.rerun()
                else:
                    st.session_state.final_df = pd.DataFrame()
                    st.session_state.busqueda_realizada = True
                    st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    # --- 5. RESULTADOS ---
    if st.session_state.busqueda_realizada:
        df_res = st.session_state.get('final_df')

        if df_res is not None and not df_res.empty:
            st.markdown("### 🏥 Las 3 Mejores Opciones")
            
            # Priorización por Plan
            mapeo_p = {"Premium": 0, "Pro": 1, "Básico": 2}
            df_res['Prioridad_Plan'] = df_res['Plan'].str.capitalize().map(mapeo_p).fillna(2)
            top_3 = df_res.sort_values(['Prioridad_Plan', 'Precio' if prio=="Precio" else 'Km']).head(3)

            for i, (index, fila) in enumerate(top_3.iterrows()):
                plan = fila['Plan'].capitalize()
                color = {"Premium": "#D4AF37", "Pro": "#C0C0C0", "Básico": "#CD7F32"}.get(plan, "#CD7F32")
                
                # Card HTML
                st.markdown(f"""
                <div style="border: 2px solid {color if i==0 else '#EEE'}; padding: 15px; border-radius: 12px; background: white; color: black; margin-bottom: 10px;">
                    <h4 style="margin:0; color:#004D40;">{fila['Nombre']}</h4>
                    <p style="margin:5px 0;">💰 <b>${fila['Precio']}</b> • 📍 <b>{fila['Km']:.1f} km</b></p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Seleccionar {fila['Nombre']}", key=f"sel_{index}"):
                    st.session_state.sede_seleccionada = fila
                    st.rerun()
        else:
            st.info("✨ No encontramos sedes para este estudio. ¡Estamos trabajando en ello!")

    # --- F. DETALLE DE SELECCIÓN (MAPA CENTRADO Y ESTILO FINAL) ---
if st.session_state.get('sede_seleccionada') is not None:
    mostrar = st.session_state.sede_seleccionada
    
    try:
        # 1. Variables y Lógica de Colores (Plan Básico en Azul)
        est_n = st.session_state.get('estudio_buscado', 'el estudio solicitado')
        nombre_clinica = mostrar.get('Nombre', 'la clínica')
        precio_raw = mostrar.get('Precio')
        precio_f = f"{precio_raw}" if precio_raw and str(precio_raw).lower() != 'none' and not pd.isna(precio_raw) else "a consultar"
        
        wa_num = str(mostrar.get('Whatsapp', '584120000000')).split('.')[0]
        lat_dest, lon_dest = mostrar.get('Latitud'), mostrar.get('Longitud')

        plan_raw = str(mostrar.get('Plan', 'Básico')).strip().capitalize()
        colores_plan = {
            "Premium": "#D4AF37", # Dorado
            "Pro": "#C0C0C0",     # Plata
            "Básico": "#4285F4"   # Azul (Confirmado como perfecto)
        }
        color_tema = colores_plan.get(plan_raw, "#4285F4")

       # --- 2. RENDERIZADO DE TARJETA XL CENTRADA ---
        st.markdown(f"""
            <div style="border: 5px solid {color_tema}; padding: 35px; border-radius: 25px; background-color: white; color: black; margin-top: 10px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
                <span style="background-color: {color_tema}; color: white; padding: 6px 18px; border-radius: 12px; font-size: 0.9rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px;">
                    Plan {plan_raw}
                </span>
                <h2 style="margin: 20px 0 10px 0; color: #004D40; font-size: 2.3rem; font-weight: 900; line-height: 1.1;">
                    {nombre_clinica}
                </h2>
                <div style="width: 80px; height: 4px; background-color: {color_tema}; margin: 15px auto 25px auto; border-radius: 2px;"></div>
                <p style="font-size: 1.5rem; margin: 0; color: #101828; font-weight: 500;">
                    💰 <b>Presupuesto:</b> ${precio_f}<br>
                    📝 <b>Estudio:</b> {est_n}
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # --- EXPLICACIÓN POR IA ---
        with st.expander("💡 ¿Qué es este estudio?", expanded=False):
            # Aquí llamamos a la función enviándole el nombre del estudio actual
            descripcion_ia = obtener_concepto_estudio(est_n) 
            st.write(descripcion_ia)

        # --- 3. BOTONERA UNIFICADA ---
        st.write("")
        # Botón de añadir (Ahora integrado visualmente arriba de los otros)
        if st.button(f"➕ AÑADIR {est_n.upper()} AL PRESUPUESTO", key=f"btn_add_{nombre_clinica}", use_container_width=True):
    # Pasamos est_n, precio_raw y nombre_clinica
            if agregar_al_carrito(est_n, precio_raw, nombre_clinica):
                st.toast(f"✅ Añadido a la lista", icon="🛒")
            else:
                st.toast(f"⚠️ Ya está en la lista", icon="📋")

        # Botones de contacto y compartir
        cuerpo_mensaje = urllib.parse.quote(f"Estimados, gusto en saludarles. Estoy interesado en realizarme el examen de *{est_n}* en su sede de *{nombre_clinica}*. Vi su presupuesto de *${precio_f}* a través de *BioData*.")
        mensaje_compartir = f"🏥 *OPCIÓN MÉDICA - BIO DATA*\n\n🔬 *Estudio:* {est_n}\n📍 *Sede:* {nombre_clinica}\n💰 *Costo:* ${precio_f}\n📱 *WhatsApp:* +{wa_num}"
        texto_sh = urllib.parse.quote(mensaje_compartir)
        g_maps_url = f"https://www.google.com/maps/search/?api=1&query={lat_dest},{lon_dest}"

        html_botones = f"""
        <div style="display: flex; flex-direction: column; gap: 14px; font-family: sans-serif; margin-top: 10px;">
            <a href="https://wa.me/{wa_num}?text={cuerpo_mensaje}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #25D366; color: white !important; padding: 18px; border-radius: 15px; text-align: center; font-weight: 800; font-size: 17px;">📲 CONTACTAR POR WHATSAPP</div>
            </a>
            <a href="{g_maps_url}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #4285F4; color: white !important; padding: 18px; border-radius: 15px; text-align: center; font-weight: 800; font-size: 17px;">📍 CÓMO LLEGAR (GOOGLE MAPS)</div>
            </a>
            <a href="https://api.whatsapp.com/send?text={texto_sh}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #FF9800; color: white !important; padding: 18px; border-radius: 15px; text-align: center; font-weight: 800; font-size: 17px;">🔗 COMPARTIR INFORMACIÓN</div>
            </a>
        </div>
        """
        st.components.v1.html(html_botones, height=280)

        # --- 4. MI PRESUPUESTO (DISEÑO RESALTADO) ---
        if st.session_state.get('carrito'):
            st.write("---")
            
            # Título llamativo con fondo amarillo
            st.markdown("""
                <div style="background-color: #FFD700; padding: 10px; border-radius: 10px 10px 0 0; text-align: center;">
                    <h3 style="color: black; margin: 0;"> REVISAR MI PRESUPUESTO POR SEDES</h3>
                </div>
            """, unsafe_allow_html=True)
            
            # El expander ahora parece parte del bloque amarillo
            with st.expander("Haz clic aquí para ver el detalle de tus estudios", expanded=True):
                total_general = 0
                sedes_agrupadas = {}
                
                for item in st.session_state.carrito:
                    sede = item.get('sede', 'Clínica por definir') 
                    if sede not in sedes_agrupadas:
                        sedes_agrupadas[sede] = []
                    sedes_agrupadas[sede].append(item)

                for sede, estudios in sedes_agrupadas.items():
                    st.markdown(f"##### 🏥 {sede}")
                    subtotal_sede = 0
                    
                    for est in estudios:
                        c1, c2 = st.columns([4, 1])
                        c1.caption(f"• {est['estudio']}")
                        c2.caption(f"${est.get('precio', 0)}")
                        subtotal_sede += est.get('precio', 0)
                    
                    total_general += subtotal_sede
                    st.markdown(f"<p style='text-align: right; color: #4285F4; font-weight: bold;'>Subtotal en sede: ${subtotal_sede:.2f}</p>", unsafe_allow_html=True)
                    st.write("") 

                st.divider()
                st.markdown(f"<h2 style='text-align: center; color: #101828;'>Total General: ${total_general:.2f}</h2>", unsafe_allow_html=True)

                # 3. Generación y descarga del PDF
            try:
                pdf_output = generar_pdf_presupuesto(st.session_state.carrito, total_general)
                st.download_button(
                    label="📄 DESCARGAR MI PRESUPUESTO (PDF)",
                    data=bytes(pdf_output),
                    file_name="Presupuesto_BioData.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_pdf_btn"
                )
            except Exception as e_pdf:
                st.error(f"Error al preparar el PDF: {e_pdf}")
                
                if st.button("🗑️ Vaciar Todo el Presupuesto", use_container_width=True, key="btn_vaciar_final"):
                    st.session_state.carrito = []
                    st.rerun()

                    # ... (Debajo del botón de Vaciar Todo)
                
                pdf_bytes = generar_pdf_presupuesto(st.session_state.carrito, total_general)
                
                st.download_button(
                    label="📄 DESCARGAR PRESUPUESTO (PDF)",
                    data=pdf_bytes,
                    file_name="Presupuesto_BioData.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                # Preparamos los datos para el PDF
                total_general = sum(item.get('precio', 0) for item in st.session_state.carrito)

        # --- 5. MAPA DE UBICACIÓN (AL FINAL) ---
        st.write("### 📍 Ubicación de la Sede")
        u_lat = st.session_state.get('u_lat', 10.4806)
        u_lon = st.session_state.get('u_lon', -66.9036)
        
        m_ruta = folium.Map(location=[(u_lat + lat_dest)/2, (u_lon + lon_dest)/2], zoom_start=14)
        folium.Marker([u_lat, u_lon], tooltip="Tú", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m_ruta)
        folium.Marker([lat_dest, lon_dest], tooltip=nombre_clinica, icon=folium.Icon(color='red', icon='plus', prefix='fa')).add_to(m_ruta)

        folium_static(m_ruta, height=450)

    except Exception as e:
        st.error(f"Error en la visualización: {e}")
       
# --- 7. CONTENIDO EMPRESA (OJO: Asegúrate que el carrito NO esté dentro de este elif) ---   
elif st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver", key="back_e"): 
        st.session_state.perfil = None
        st.rerun()
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
