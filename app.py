import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN Y ESTILO (Cópialo tal cual para el look de la imagen) ---
st.set_page_config(page_title="BioData", page_icon="🔍", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    [data-testid="stHeader"], header, #MainMenu, footer { visibility: hidden; }
    .stApp { background-color: #F8F9FA !important; font-family: 'Inter', sans-serif; }

    /* LOGO Y SLOGAN */
    .main-logo { color: #00796B; font-size: 5rem; font-weight: 800; text-align: center; margin-bottom: -15px; letter-spacing: -3px; line-height: 1; }
    .slogan { color: #37474F; font-size: 1.5rem; text-align: center; font-weight: 400; margin-bottom: 40px; }

    /* CONTENEDORES (CARDS) */
    .result-card {
        background-color: white !important;
        border-radius: 25px !important;
        padding: 25px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05) !important;
        border: 1px solid #ECEFF1 !important;
        margin-bottom: 20px !important;
        text-align: center;
    }
    .med-info-box { 
        background: linear-gradient(135deg, #00796B 0%, #26A69A 100%) !important; 
        padding: 20px; border-radius: 20px; color: white !important;
        margin-bottom: 20px; text-align: center;
    }

    /* BOTONES */
    div.stButton > button { 
        background-color: #00796B !important; color: white !important; 
        font-weight: 700 !important; border-radius: 50px !important; 
        border: none !important; padding: 12px 25px !important;
    }
    .btn-contactar {
        background-color: #25D366 !important; color: white !important;
        text-align: center; padding: 15px !important; border-radius: 50px !important;
        font-weight: 800 !important; display: block !important; text-decoration: none !important;
    }
    .btn-share {
        background-color: #F1F3F4 !important; color: #5F6368 !important;
        text-align: center; padding: 10px !important; border-radius: 50px !important;
        font-size: 0.9rem !important; display: block !important; text-decoration: none !important;
        border: 1px solid #E0E0E0 !important; margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LÓGICA DE NAVEGACIÓN ---
if 'perfil' not in st.session_state: 
    st.session_state.perfil = None

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

# --- 3. SECCIÓN PACIENTE (AQUÍ ES DONDE OCURRE LA MAGIA) ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver"):
        st.session_state.perfil = None; st.rerun()

    busqueda = st.text_input("🔍 ¿Qué estudio necesitas?", placeholder="Ej: OCT de mácula o sube tu orden...")

    if busqueda:
        # 1. CUADRO DE ESTUDIO DETECTADO
        st.markdown(f"""
            <div class="med-info-box">
                <small>ESTUDIO DETECTADO</small>
                <h3 style='margin:0; color:white;'>{busqueda.upper()}</h3>
            </div>
        """, unsafe_allow_html=True)

        # --- AQUÍ VA TU LÓGICA EXISTENTE DE SUPABASE PARA BUSCAR LA CLÍNICA ---
        # (Usa tus variables reales: clinica_nombre, precio_estudio, etc.)
        
        col_res, col_map = st.columns([1, 1.2])

        with col_res:
            # 2. CUADRO DE MEJOR OPCIÓN
            st.markdown(f"""
                <div class="result-card">
                    <p style='color:#D4AF37; font-weight:800; font-size:0.8rem;'>💎 ALIADO PREMIUM</p>
                    <h2 style='margin:0; color:#263238;'>Oftalmo Plus</h2>
                    <h1 style='margin:10px 0; color:#263238; font-size:3.5rem;'>$85</h1>
                    <p style='color:#607D8B;'>📍 A 2.1 km de distancia</p>
                    <a href="#" class="btn-contactar">📲 CONTACTAR</a>
                    <a href="#" class="btn-share">🔗 COMPARTIR RESULTADO</a>
                </div>
            """, unsafe_allow_html=True)

        with col_map:
            # 3. CUADRO DE MAPA
            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            st.write("📍 **UBICACIÓN ESTIMADA**")
            # st.map(tu_data_de_mapa) # Reemplaza con tu función de mapa real
            st.image("https://via.placeholder.com/400x300.png?text=Mapa+Interactivo", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# --- 4. SECCIÓN EMPRESA (MANTÉN TU LÓGICA AQUÍ) ---
if st.session_state.perfil == 'empresa':
    if st.button("⬅️ Volver"):
        st.session_state.perfil = None; st.rerun()
    st.title("Portal de Clínicas")
    # Tu código de carga de Excel y GitHub va aquí...
