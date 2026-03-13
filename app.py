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

# --- CONFIGURACIÓN DE BASE DE DATOS (Pégalo aquí) ---
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def actualizar_precio_supabase(id_registro, nuevo_precio):
    try:
        # Reemplaza 'nombre_de_tu_tabla' por el nombre real en Supabase (ej. 'servicios' o 'inventario')
        response = supabase.table("servicios").update({"Precio": nuevo_precio}).eq("id", id_registro).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar: {e}")
        return False

def generar_pdf_gerencial(nombre_clinica, estudios, cuota, demanda, posicion, narrativa, plan_raw):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Título Principal con Branding de Aliado
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(31, 73, 125) # Azul BioData
    pdf.cell(0, 15, "INFORME ESTRATEGICO - ALIADO BIODATA", ln=True, align='C')
    pdf.set_draw_color(31, 73, 125)
    pdf.line(10, 25, 200, 25)
    pdf.ln(10)
    
    # 2. Identificación del Aliado
    # Transformamos "Plan Pro" en "Aliado Pro"
    etiqueta_aliado = f"Aliado {plan_raw.replace('Plan', '').strip()}"
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, f"Institucion: {nombre_clinica}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
    pdf.cell(0, 10, f"Estatus: {etiqueta_aliado}", ln=True)
    pdf.cell(0, 10, f"Analisis de: {', '.join(estudios)}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
    pdf.ln(5)
    
    # 3. Cuadro de Indicadores
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "  RESUMEN DE INDICADORES", ln=True, fill=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f" - Cuota de Mercado: {cuota:.1f}%", ln=True)
    pdf.cell(0, 8, f" - Demanda Local Detectada: {demanda} busquedas", ln=True)
    pdf.cell(0, 8, f" - Posicionamiento: {posicion}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
    pdf.ln(10)
    
    # 4. Narrativa Ejecutiva
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "INTERPRETACION ESTRATEGICA PARA GERENCIA", ln=True)
    pdf.set_font("Arial", '', 10)
    
    # Limpieza de Markdown y caracteres especiales
    texto_limpio = narrativa.replace('**', '')
    texto_final = texto_limpio.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.multi_cell(0, 6, texto_final)
    
    # Pie de página
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 10, "Documento exclusivo para Aliados BioData AI. Prohibida su reproduccion total o parcial.", align='C', ln=True)
    
    return pdf.output()

@st.cache_data(ttl=86400) # Guarda el resultado por 24 horas para ahorrar créditos
def obtener_concepto_estudio(nombre_estudio):
    if not nombre_estudio:
        return "Información no disponible."

    # --- 1. DICCIONARIO LOCAL (El "Cinturón de Seguridad") ---
    # Aquí puedes agregar todos los estudios que quieras pre-definir
    diccionario_estudios = {
        "campo visual": "Prueba que mide la amplitud de la visión y ayuda a detectar problemas en el nervio óptico o retina.",
        "oct nervio optico": "Es el estándar de oro para diagnosticar y monitorear el glaucoma, ya que permite medir el grosor de las fibras antes de que se pierda la visión.",
        "oct macula": "Detecta enfermedades como la degeneración macular, edema macular (inflamación) o agujeros maculares. Permite ver cortes transversales de la retina con precisión microscópica.",
        "biometria": "Es esencial antes de una cirugía de cataratas. Los datos obtenidos se introducen en fórmulas matemáticas para calcular la potencia del lente intraocular que se le implantará al paciente.",
        "topografia corneal": "Analiza la curvatura y regularidad de la córnea. Se usa para detectar queratocono, adaptar lentes de contacto especiales o evaluar si un paciente es candidato a cirugía láser (LASIK).",
        "ecografia ocular": "Evalua el estado de la retina y el humor vítreo. Es clave para detectar desprendimientos de retina, tumores intraoculares o cuerpos extraños tras un traumatismo."
    }

    # Limpiamos el nombre para buscar en el diccionario (minúsculas y sin espacios extra)
    nombre_limpio = nombre_estudio.lower().strip()

    # Si el estudio está en nuestro diccionario, lo devolvemos de inmediato
    if nombre_limpio in diccionario_estudios:
        return diccionario_estudios[nombre_limpio]

    # --- 2. LLAMADA A LA IA (Solo si no está en el diccionario) ---
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Probamos con el modelo más estable
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"Define brevemente qué es el estudio médico {nombre_estudio}. Máximo 20 palabras."
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text
            
    except Exception as e:
        # Si la IA falla (por cuota o error 429), damos una respuesta genérica amigable
        print(f"Error IA: {e}") # Esto se verá en tus logs
        return "Detalles de preparación y concepto disponibles al momento de agendar su cita."

    return "Información disponible en la sede médica."

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
    
    # 1. INICIALIZACIÓN DE ESTADO
    if 'u_lat' not in st.session_state:
        st.session_state.u_lat, st.session_state.u_lon = 10.4806, -66.9036
    if 'busqueda_realizada' not in st.session_state:
        st.session_state.busqueda_realizada = False
    if 'sede_seleccionada' not in st.session_state:
        st.session_state.sede_seleccionada = None

    st.title("🔍 Buscador de Estudios")

    # (Botones de volver y avisos de carrito...)
    if st.button("⬅️ Volver al Inicio", key="back_p"): 
        st.session_state.perfil = None
        st.session_state.busqueda_realizada = False
        st.rerun()

    # --- 2. UBICACIÓN Y FILTROS ---
    st.markdown("### 📍 ¿Dónde te encuentras?")
    loc = get_geolocation(component_key="gps_manual_definitivo")
    if loc:
        st.session_state.u_lat = loc['coords']['latitude']
        st.session_state.u_lon = loc['coords']['longitude']
    
    c1, c2 = st.columns(2)
    with c1: 
        prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True, key="sort_radio")
    with c2: 
        manual = st.text_input("⌨️ ¿Qué examen buscas?", key="exam_input")
    
    up_img = st.file_uploader("O sube foto de la orden", type=["jpg", "jpeg", "png"])

    # --- 3. CARGA DE DATOS (DENTRO DEL PERFIL PERSONA) ---
    if 'df_maestro' not in st.session_state:
        try:
            df_temp = pd.read_excel("base_clinicas.xlsx")
            df_temp.columns = [str(c).strip().capitalize() for c in df_temp.columns]
            try:
                res_p = supabase.table("precios_servicios").select("*").execute()
                df_upd = pd.DataFrame(res_p.data)
                if not df_upd.empty:
                    for _, fila in df_upd.iterrows():
                        mask = (df_temp['Nombre'] == fila['clinica']) & (df_temp['Estudio'] == fila['estudio'])
                        df_temp.loc[mask, 'Precio'] = fila['precio']
            except: pass 
            st.session_state.df_maestro = df_temp
        except Exception as e:
            st.error(f"Error cargando base: {e}")

    # --- 4. BOTÓN BUSCAR (Asegúrate de que esté alineado dentro de 'if persona') ---
if st.button("🚀 BUSCAR MEJORES OPCIONES", key="main_search"):
    try:
        with st.spinner('Analizando solicitud...'):
            # 1. Limpiamos búsquedas anteriores para evitar conflictos
            st.session_state.busqueda_realizada = False
            st.session_state.sede_seleccionada = None
            
            # 2. Usamos la memoria maestra
            df_local = st.session_state.df_maestro.copy() 

            # 3. Identificar estudio (IA)
            if manual: 
                n_est, d_est = analizar_texto_ai(manual)
            elif up_img: 
                n_est, d_est = analizar_imagen_ai(up_img.getvalue())
            else:
                st.warning("⚠️ Ingresa un examen."); st.stop()

            # 4. Normalización y filtrado (Versión Ultra-Flexible)
            def norm(t): return ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
            palabras = [p for p in norm(n_est).split() if len(p) > 2]
            
            # Filtro que busca CUALQUIER palabra clave en la columna 'Estudio'
            res_df = df_local[df_local['Estudio'].astype(str).apply(lambda x: any(p in norm(x) for p in palabras))].copy()

            # 5. Si hay resultados, calculamos y GUARDAMOS EN SESIÓN
            if not res_df.empty:
                res_df['Km'] = res_df.apply(lambda r: calcular_distancia(st.session_state.u_lat, st.session_state.u_lon, float(r['Latitud']), float(r['Longitud'])), axis=1)
                
                # GUARDADO CRUCIAL
                st.session_state.final_df = res_df.sort_values('Precio' if prio == "Precio" else 'Km')
                st.session_state.estudio_buscado = n_est
                st.session_state.busqueda_realizada = True
                st.rerun() # Esto obliga a Streamlit a ver los cambios
            else:
                st.session_state.final_df = pd.DataFrame()
                st.session_state.busqueda_realizada = True
                st.rerun()
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")

    # --- 5. VISUALIZACIÓN DE RESULTADOS ---
# Forzamos la lectura de la sesión
if st.session_state.get('busqueda_realizada') == True:
    
    # Si la sede está seleccionada, mostramos la Tarjeta XL
    if st.session_state.get('sede_seleccionada') is not None:
        # (Aquí va tu código de la Tarjeta XL)
        pass
    
    # Si no hay sede seleccionada, mostramos la lista
    else:
        res_df = st.session_state.get('final_df', pd.DataFrame())
        
        if not res_df.empty:
            st.write("### 🏥 Opciones Disponibles")
            # (Aquí va tu código de las tarjetas cortas y el TOP 3)
        else:
            st.error(f"No encontramos resultados para '{st.session_state.get('estudio_buscado')}'.")
            st.info("💡 Prueba escribiendo solo una palabra clave (ej: 'Resonancia' en vez de 'Resonancia de rodilla').")

# --- 7. CONTENIDO EMPRESA (AL MISMO NIVEL QUE EL IF PERSONA) ---   
elif st.session_state.perfil == 'empresa':
    st.title("🏢 Panel de Control de Clínica")
    if st.button("⬅️ Volver", key="back_e"): 
        st.session_state.perfil = None
        st.rerun()
    # Aquí va tu código de inventario y actualización de precios
        

    st.title("🏥 Portal de Gestión")
    clave = st.text_input("Clave de Acceso", type="password", key="pass_e")
    
    if clave in ACCESOS_CLINICAS:
        nombre_c = ACCESOS_CLINICAS[clave]
        st.success(f"Sesión activa: {nombre_c}")
        
        tab_stats, tab_premium, tab_oferta, tab_inventario = st.tabs([
            "📊 Estadísticas", "💎 ANÁLISIS PREMIUM", "⚡ OFERTA RELÁMPAGO", "🛠️ GESTIÓN DE INVENTARIO"
        ])
        
        # --- PESTAÑA 1: ESTADÍSTICAS ---
        with tab_stats:
            c_f1, c_f2 = st.columns(2)
            f_ini = c_f1.date_input("Desde:", date.today() - timedelta(days=7), key="f_ini_stat")
            f_fin = c_f2.date_input("Hasta:", date.today(), key="f_fin_stat")
    
            try:
                resp = supabase.table("busquedas_stats") \
                    .select("*") \
                    .gte("fecha", f_ini.isoformat()) \
                    .lte("fecha", (f_fin + timedelta(days=1)).isoformat()) \
                    .execute()
                
                df_stats = pd.DataFrame(resp.data)
                
                if not df_stats.empty:
                    df_stats['estudio'] = df_stats['estudio'].str.strip().str.upper()
                    df_stats = df_stats[~df_stats['estudio'].str.contains("NOMBRE", na=False)]
                    
                    st.metric("Búsquedas en este rango", len(df_stats))
                    
                    top_data = df_stats['estudio'].value_counts().head(5).reset_index()
                    top_data.columns = ['estudio', 'conteo']
                    
                    st.subheader("📊 Top 5 Estudios Más Buscados")
                    chart = alt.Chart(top_data).mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10).encode(
                        x=alt.X('estudio', sort='-y', title="Estudio", axis=alt.Axis(labelAngle=-45)),
                        y=alt.Y('conteo', title="Consultas"),
                        color=alt.Color('estudio', scale=alt.Scale(scheme='blues'), legend=None)
                    ).properties(height=400)
                    
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("ℹ️ No hay registros para las fechas seleccionadas.")
            except Exception as e:
                st.error(f"Error en estadísticas: {e}")

       # --- PESTAÑA 2: PREMIUM (VERSIÓN BLINDADA) ---
        with tab_premium:
            es_premium = "Premium" in clave or nombre_c == "ADMIN"
            
            if es_premium:
                st.subheader("💎 Panel de Inteligencia de Mercado")
                try:
                    # 1. Carga inicial del Excel
                    df_raw = pd.read_excel("base_clinicas.xlsx")
                    df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]
                    
                    def encontrar_columna(lista_posibles, df):
                        for c in df.columns:
                            for posible in lista_posibles:
                                if posible in c: return c
                        return None

                    col_lat = encontrar_columna(['lat'], df_raw)
                    col_lon = encontrar_columna(['lon', 'lng'], df_raw)
                    col_nom = encontrar_columna(['nom', 'clini'], df_raw)
                    col_est = encontrar_columna(['estu', 'tipo'], df_raw)
                    col_pre = encontrar_columna(['pre', 'cost'], df_raw)

                    if not col_lat or not col_lon:
                        st.error("❌ No se encontraron coordenadas en el Excel.")
                        st.stop()

                    df_raw = df_raw.rename(columns={col_lat:'Lat', col_lon:'Lon', col_nom:'Nombre', col_est:'Estudio', col_pre:'Precio'})
                    
                    # Limpieza
                    df_raw['Nombre'] = df_raw['Nombre'].astype(str).str.strip()
                    df_raw['Estudio'] = df_raw['Estudio'].astype(str).str.strip()
                    for c in ['Precio', 'Lat', 'Lon']: df_raw[c] = pd.to_numeric(df_raw[c], errors='coerce')
                    
                    df_completo = df_raw.dropna(subset=['Precio', 'Estudio']).copy()
                    estudios_sel = st.multiselect("Estudios:", options=sorted(df_completo['Estudio'].unique().tolist()), key="premium_v4")

                    if estudios_sel:
                        df_comp = df_completo[df_completo['Estudio'].isin(estudios_sel)].copy()
                        
                        if not df_comp.empty:
                            # --- SECCIÓN 1: MARKET SHARE ---
                            share = df_comp.groupby('Nombre').size().reset_index(name='Sedes')
                            total_sedes = float(share['Sedes'].sum())
                            share['%'] = (share['Sedes'] / total_sedes) * 100
                            
                            c1, c2 = st.columns([1, 1.2])
                            with c1: st.dataframe(share.sort_values('%', ascending=False), hide_index=True)
                            with c2:
                                import plotly.express as px
                                fig = px.pie(share, values='%', names='Nombre', hole=0.4)
                                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
                                st.plotly_chart(fig, use_container_width=True)

                            # --- SECCIÓN 2: PRECIOS ---
                            st.markdown("---")
                            p_promedio = float(df_comp['Precio'].mean())
                            tu_p_df = df_comp[df_comp['Nombre'].str.contains(nombre_c, case=False, na=False)]
                            tp = float(tu_p_df['Precio'].mean()) if not tu_p_df.empty else 0.0
                            
                            m1, m2, m3 = st.columns(3)
                            if tp > 0:
                                m1.metric("Tu Precio", f"${tp:.0f}", f"{((tp-p_promedio)/p_promedio)*100:+.1f}%", delta_color="inverse")
                            else:
                                m1.metric("Tu Precio", "N/R")
                            m2.metric("Mínimo", f"${float(df_comp['Precio'].min()):.0f}")
                            m3.metric("Promedio", f"${p_promedio:.0f}")

                            # --- SECCIÓN 3: MAPA ---
                            st.markdown("---")
                            st.markdown("#### 📍 Mapa de Calor")
                            try:
                                resp_map = supabase.table("busquedas_stats").select("lat, lon").gte("fecha", f_ini.isoformat()).lte("fecha", (f_fin + timedelta(days=1)).isoformat()).execute()
                                df_mapa = pd.DataFrame(resp_map.data)
                                if not df_mapa.empty:
                                    pts = df_mapa.dropna(subset=['lat', 'lon'])[['lat', 'lon']].values.tolist()
                                    import folium
                                    from streamlit_folium import folium_static
                                    from folium.plugins import HeatMap
                                    m_p = folium.Map(location=[10.48, -66.90], zoom_start=12)
                                    HeatMap(pts).add_to(m_p)
                                    folium_static(m_p)
                            except: st.info("Cargando mapa...")

                            # --- GUÍA DE CONCEPTOS (AYUDA PARA EL USUARIO) ---
                            with st.expander("❓ ¿Qué significan estos indicadores?"):
                                st.markdown("""
                                * **📊 Cuota de Mercado:** Porcentaje de sedes físicas que posee tu clínica frente al total de la competencia analizada.
                                * **🔥 Demanda Local:** Volumen de búsquedas reales detectadas en el sistema. Indica qué tan interesado está el público en este estudio actualmente.
                                * **🎯 Posicionamiento:** Diferencia porcentual de tus precios frente al promedio. (+) significa precio Premium, (-) significa precio Competitivo.
                                * **💰 Diagnóstico de Precios:** Análisis de la IA sobre si tu precio actual es una barrera o una ventaja para captar pacientes.
                                * **📍 Diagnóstico Geográfico:** Cruce entre la ubicación de la demanda y tu presencia física. Detecta si estás perdiendo pacientes por falta de cobertura.
                                """)

                            # --- SECCIÓN 4: CONSULTOR ESTRATÉGICO BIODATA AI (ROBUSTO) ---
                            st.markdown("---")
                            st.subheader("🤖 Consultoría Estratégica Avanzada")

                            try:
                                # Recalculamos localmente para evitar errores de 'not defined'
                                share_ia = df_comp.groupby('Nombre').size().reset_index(name='Sedes')
                                total_m = float(share_ia['Sedes'].sum())
                                mi_sedes = float(share_ia[share_ia['Nombre'].str.contains(nombre_c, case=False, na=False)]['Sedes'].sum())
                                cuota_m = (mi_sedes / total_m) * 100 if total_m > 0 else 0
                                
                                avg_m = float(df_comp['Precio'].mean())
                                n_pts = len(pts) if 'pts' in locals() else 0

                                # 1. Métricas de Impacto
                                c_ia1, c_ia2, c_ia3 = st.columns(3)
                                
                                with c_ia1:
                                    st.metric("Cuota de Mercado", f"{cuota_m:.1f}%")
                                with c_ia2:
                                    st.metric("Demanda Local", f"{n_pts} pts", "🔥 Alta" if n_pts > 50 else "🌤️ Normal")
                                with c_ia3:
                                    diff_p = ((tp - avg_m) / avg_m) * 100 if avg_m > 0 else 0
                                    st.metric("Posicionamiento", f"{diff_p:+.1f}%", "vs Promedio")

                                # 2. Análisis Dinámico
                                col_info1, col_info2 = st.columns(2)
                                
                                with col_info1:
                                    st.markdown("**🎯 Diagnóstico de Precios**")
                                    if tp > avg_m:
                                        st.warning(f"Tu tarifa es superior al mercado. BioData IA sugiere enfocar el marketing en **'Tecnología de Punta'** y **'Atención VIP'**.")
                                    elif tp > 0:
                                        st.success(f"Tienes ventaja competitiva en precio. BioData IA sugiere campañas de **'Volumen'** para capturar el {100-cuota_m:.1f}% restante del mercado.")
                                    else:
                                        st.info("No hemos detectado tus precios en la base de datos para este estudio.")

                                with col_info2:
                                    st.markdown("**📍 Diagnóstico Geográfico**")
                                    if n_pts > 50 and cuota_m < 15:
                                        st.error("🚨 **Oportunidad Crítica**: Hay una altísima demanda en zonas donde tu presencia es baja. Estás perdiendo pacientes frente a la competencia.")
                                    else:
                                        st.info("Tu cobertura actual es adecuada para el volumen de búsquedas detectado en el sistema.")

                                # 3. Recomendación Maestra
                                st.markdown("---")
                                if cuota_m < 20 and tp > avg_m:
                                    rec_ia = "Implementar un 'Bono de Primera Visita' para reducir la barrera de entrada al servicio premium."
                                elif n_pts > 70:
                                    rec_ia = "Activar 'Ofertas Relámpago' (Pestaña siguiente) de inmediato para absorber el pico de demanda actual."
                                else:
                                    rec_ia = "Mantener estrategia actual y reforzar la fidelización de pacientes existentes."
                                
                                st.success(f"💡 **ESTRATEGIA RECOMENDADA:** {rec_ia}")

                                # 4. Interpretación Ejecutiva (Narrativa)
                                st.markdown("---")
                                st.markdown("### 🗣️ Resumen de Lectura para Gerencia")
                                
                                # Construcción lógica de la narrativa
                                p_pos = "competitivo" if diff_p < 0 else "premium"
                                p_delta = f"({abs(diff_p):.1f}% {'bajo' if diff_p < 0 else 'sobre'} el promedio)"
                                
                                narrativa = f"""
                                **Doctor, según el análisis de BioData IA:** Actualmente manejamos una **Cuota de Mercado de {cuota_m:.1f}%**, 
                                mientras que la **Demanda Local** es {'altísima' if n_pts > 50 else 'moderada'} ({n_pts} búsquedas detectadas). 
                                
                                Dado que nuestro **Posicionamiento** es {p_pos} {p_delta}, 
                                el **Diagnóstico de Precios** sugiere que { 'es el momento ideal para lanzar una oferta y capturar pacientes rápidamente' if diff_p <= 0 else 'debemos reforzar nuestra propuesta de valor para justificar el precio premium'}. 
                                
                                Finalmente, el **Diagnóstico Geográfico** indica que {'existe una oportunidad de expansión o captación agresiva' if (n_pts > 50 and cuota_m < 20) else 'nuestra cobertura es estable'}, 
                                permitiéndonos {'adelantarnos a la competencia en zonas desatendidas' if n_pts > 50 else 'fidelizar nuestra base actual de pacientes'}.
                                """
                                
                                st.info(narrativa)

                                # --- SECCIÓN DE DESCARGA PDF ---
                                st.markdown("---")
                                try:
                                    # 1. Intentamos rescatar el plan de la sesión o definimos uno por defecto
                                    # Buscamos en el dataframe original el plan de esta clínica específica
                                    try:
                                        plan_actual = df_comp[df_comp['Nombre'] == nombre_c]['Plan'].iloc[0]
                                    except:
                                        plan_actual = "Premium" # Respaldo si no se encuentra

                                    # 2. Generamos los bytes llamando a la función revisada
                                    pdf_output = generar_pdf_gerencial(
                                        nombre_c, 
                                        estudios_sel, 
                                        cuota_m, 
                                        n_pts, 
                                        f"{p_pos} {p_delta}", 
                                        narrativa,
                                        plan_actual # Enviamos el plan rescatado
                                    )
                                    
                                    # 3. El botón de descarga
                                    st.download_button(
                                        label="📥 Descargar Informe para Gerencia (PDF)",
                                        data=bytes(pdf_output), 
                                        file_name=f"Reporte_BioData_{nombre_c}.pdf",
                                        mime="application/pdf",
                                        key="btn_descarga_final_aliado"
                                    )
                                except Exception as e_pdf:
                                    st.error(f"Nota: El reporte PDF no pudo generarse: {e_pdf}")

                            except Exception as e_ia:
                                st.error(f"Error en el procesamiento de datos Premium: {e_ia}")
                        
                        else: # Este else ahora sí corresponde al 'if' de datos suficientes
                            st.warning("No hay datos suficientes.")
                    
                    else: # Este else corresponde al 'if' de selecciona un estudio
                        st.info("👆 Selecciona un estudio.")

                except Exception as e:
                    st.error(f"Error Premium: {e}")

        # --- PESTAÑA 3: OFERTAS (ALINEADA CON WITH TAB_PREMIUM) ---
        with tab_oferta:
            st.subheader("⚡ Crear Oferta Relámpago")
            if "Pro" in clave or "Premium" in clave or nombre_c == "ADMIN":
                col1, col2 = st.columns(2)
                opciones = ["OCT de Mácula", "Campimetría", "Topografía", "Otro..."]
                sel_temp = col1.selectbox("Estudio:", opciones, key="sel_of")
                estudio_final = col1.text_input("Nombre:") if sel_temp == "Otro..." else sel_temp
                precio_of = col2.number_input("Precio ($):", min_value=1, value=50, key="num_of")
                if st.button("🪄 GENERAR CON IA"):
                    st.info(generar_copy_oferta(estudio_final, precio_of))
            else:
                st.warning("🔒 Requiere Plan PRO o PREMIUM.")
        
        # --- PESTAÑA 4: INVENTARIO ---
        with tab_inventario:
            st.subheader(f"🛠️ Gestión de Inventario - {nombre_c}")
            
            # 1. Tu bloque actual de Equipos
            with st.expander("Actualizar Estado de Equipo"):
                ce1, ce2 = st.columns(2)
                eq_sel = ce1.selectbox("Equipo:", ["OCT", "Campímetro", "Ecógrafo", "Topógrafo"], key="eq_inv")
                est_sel = ce2.radio("Estatus:", ["Operativo", "En Mantenimiento"], horizontal=True, key="st_inv")
                if st.button("Guardar Cambios"):
                    try:
                        supabase.table("inventario_equipos").insert({
                            "clinica": nombre_c, "equipo": eq_sel, "estado": est_sel, "ultima_actualizacion": datetime.now().isoformat()
                        }).execute()
                        st.success("✅ Actualizado."); time.sleep(1); st.rerun()
                    except: st.error("Error al guardar.")

            # --- NUEVO BLOQUE: ACTUALIZACIÓN DE PRECIOS ---
            with st.expander("✏️ Modificar Precios de Servicios"):
                st.info("Actualiza el valor de tus servicios en la red BioData.")
                
                # 1. CAMBIA df por st.session_state.df_maestro AQUÍ:
                servicios_aliado = st.session_state.df_maestro[st.session_state.df_maestro['Nombre'] == nombre_c]['Estudio'].unique()
                
                col_p1, col_p2 = st.columns(2)
                servicio_a_modificar = col_p1.selectbox("Servicio:", servicios_aliado, key="serv_edit_final")
                
                # 2. Y TAMBIÉN AQUÍ PARA BUSCAR EL PRECIO ACTUAL:
                precio_actual = st.session_state.df_maestro[
                    (st.session_state.df_maestro['Nombre'] == nombre_c) & 
                    (st.session_state.df_maestro['Estudio'] == servicio_a_modificar)
                ]['Precio'].values[0]
                
                nuevo_precio = col_p2.number_input("Nuevo Precio ($):", value=float(precio_actual), step=5.0, key="price_edit_final")
                
                if st.button("Confirmar y Publicar Nuevo Precio"):
                    try:
                        # El UPSERT busca por 'clinica' y 'estudio' (deben ser únicos o estar configurados)
                        # Para que funcione como actualización, Supabase necesita saber qué fila es, 
                        # o simplemente insertamos el nuevo registro de cambio.
                        supabase.table("precios_servicios").upsert({
                            "clinica": nombre_c, 
                            "estudio": servicio_a_modificar, 
                            "precio": nuevo_precio,
                            "ultima_actualizacion": datetime.now().isoformat()
                        }).execute()
                        
                        st.success(f"✅ ¡Cambio guardado! El nuevo precio de {servicio_a_modificar} es ${nuevo_precio}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al conectar con Supabase: {e}")
        
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
