import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA Y DISEÑO VISUAL (CSS) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }

    /* LOGO Y SLOGAN INICIO */
    .main-logo { color: #00796B; font-size: 5.5rem; font-weight: 800; text-align: center; margin-bottom: -15px; letter-spacing: -3px; line-height: 1; }
    .slogan { color: #37474F; font-size: 1.6rem; text-align: center; font-weight: 400; margin-bottom: 40px; }

    /* CONTENEDOR TIPO TARJETA (Cards) */
    .result-card {
        background-color: white !important;
        border-radius: 25px !important;
        padding: 25px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05) !important;
        border: 1px solid #ECEFF1 !important;
        margin-bottom: 20px !important;
        text-align: center;
    }

    /* BLOQUE DE IA (Estudio Detectado) */
    .med-info-box { 
        background: linear-gradient(135deg, #00796B 0%, #26A69A 100%) !important; 
        padding: 25px; 
        border-radius: 20px; 
        color: white !important;
        margin-bottom: 25px;
        box-shadow: 0 10px 20px rgba(0,121,107,0.15);
    }

    /* BOTONES */
    div.stButton > button { 
        background-color: #00796B !important; 
        color: white !important; 
        font-weight: 700 !important; 
        border-radius: 50px !important; 
        border: none !important; 
        padding: 12px 25px !important;
        transition: all 0.3s ease !important;
    }

    .btn-contactar {
        background-color: #25D366 !important;
        color: white !important;
        text-align: center;
        padding: 16px !important;
        border-radius: 50px !important;
        font-weight: 800 !important;
        display: block !important;
        text-decoration: none !important;
        margin-top: 15px !important;
        box-shadow: 0 4px 12px rgba(37, 211, 102, 0.2) !important;
    }

    .btn-share {
        background-color: #F1F3F4 !important;
        color: #5F6368 !important;
        text-align: center;
        padding: 10px !important;
        border-radius: 50px !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        display: block !important;
        text-decoration: none !important;
        margin-top: 10px !important;
        border: 1px solid #E0E0E0 !important;
    }

    /* TIPOGRAFÍA DE RESULTADOS */
    .study-title { color: #263238 !important; font-size: 1.5rem; font-weight: 800; margin-bottom: 10px; }
    .price-tag { color: #263238 !important; font-size: 2.8rem; font-weight: 800; margin: 10px 0; }
    .premium-label { color: #D4AF37 !important; font-weight: 800; letter-spacing: 1px; font-size: 0.8rem; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LÓGICA DE INICIO (LOGO E IMAGEN) ---
if 'perfil' not in st.session_state: st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown('<p class="main-logo">BioData</p>', unsafe_allow_html=True)
    st.markdown('<p class="slogan">Busca. Compara. Resuelve.</p>', unsafe_allow_html=True)
    
    col_p, col_e = st.columns(2)
    with col_p:
        if st.button("👤  PACIENTE", use_container_width=True):
            st.session_state.perfil = 'persona'; st.rerun()
    with col_e:
        if st.button("🏥  CLÍNICA ALIADA", use_container_width=True):
            st.session_state.perfil = 'empresa'; st.rerun()
    st.stop()

# --- 3. INTERFAZ DE BÚSQUEDA (PACIENTE) ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver"):
        st.session_state.perfil = None; st.rerun()

    st.markdown("### 🔍 ¿Qué estudio necesitas hoy?")
    busqueda = st.text_input("Sube tu orden médica o escribe el nombre del examen:")

    if busqueda:
        # SIMULACIÓN DE DETECCIÓN (Aquí va tu lógica de IA actual)
        # Solo aplicamos el diseño al resultado detectado:
        st.markdown(f"""
            <div class="med-info-box">
                <h4>📋 ESTUDIO DETECTADO</h4>
                <p style='font-size: 1.2rem; font-weight: 600;'>{busqueda.upper()}</p>
                <p>Nuestra IA ha procesado tu solicitud. Buscando mejores opciones...</p>
            </div>
        """, unsafe_allow_html=True)

        # SIMULACIÓN DE RESULTADO (Aquí va tu lógica de Supabase/Filtros)
        # Supongamos que esta es la mejor opción encontrada:
        nombre_clinica = "Oftalmo Plus"
        precio = 85
        distancia = "2.1"
        link_wa = "https://wa.me/tu_numero"

        col_res, col_map = st.columns([1, 1])

        with col_res:
            st.markdown(f"""
                <div class="result-card">
                    <p class="premium-label">💎 ALIADO PREMIUM</p>
                    <p class="study-title">{nombre_clinica}</p>
                    <p class="price-tag">${precio}</p>
                    <p>📍 A {distancia} km de tu ubicación</p>
                    <a href="{link_wa}" class="btn-contactar">📲 CONTACTAR POR WHATSAPP</a>
                    <a href="#" class="btn-share">🔗 COMPARTIR RESULTADO</a>
                </div>
            """, unsafe_allow_html=True)
        
        with col_map:
            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            st.write("📍 **UBICACIÓN EN MAPA**")
            # Aquí iría tu st.map() actual
            st.image("https://via.placeholder.com/400x300.png?text=Mapa+de+Ubicacion", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# --- 4. PORTAL DE EMPRESA (Sin cambios en lógica) ---
if st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"):
        st.session_state.perfil = None; st.rerun()
    st.title("Portal de Gestión")
    st.info("Aquí puedes actualizar tus precios y ver estadísticas de búsqueda.")
