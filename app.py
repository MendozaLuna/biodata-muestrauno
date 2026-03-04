import streamlit as st
import pandas as pd
from supabase import create_client, Client
import folium
from streamlit_folium import folium_static
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioData - Gestión de Sedes", layout="wide")

# --- CONEXIÓN SUPABASE ---
# Asegúrate de tener estas variables en tus Secrets de Streamlit
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .card { background-color: white; padding: 20px; border-radius: 15px; border-left: 5px solid #4285F4; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- LÓGICA DE SESIÓN ---
if 'perfil' not in st.session_state:
    st.session_state.perfil = None

# --- SELECTOR DE PERFIL ---
if st.session_state.perfil is None:
    st.title("🏥 Sistema BioData")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 SOY PACIENTE"):
            st.session_state.perfil = 'paciente'
            st.rerun()
    with col2:
        if st.button("⚙️ SOY ADMINISTRADOR"):
            st.session_state.perfil = 'admin'
            st.rerun()

# --- BOTÓN VOLVER ---
if st.session_state.perfil:
    if st.sidebar.button("⬅️ Cambiar Perfil"):
        st.session_state.perfil = None
        if 'final_df' in st.session_state:
            del st.session_state.final_df
        st.rerun()

# ==========================================
# --- 1. SECCIÓN PACIENTE (CON SUPABASE) ---
# ==========================================
if st.session_state.perfil == 'paciente':
    st.title("🔍 Encuentra tu Estudio Médico")
    st.info("Busca el precio más económico y la ubicación de tu examen en tiempo real.")
    
    n_est = st.text_input("¿Qué examen buscas?", placeholder="Ej: OCT, Campo Visual, Ecografía...", key="input_p")

    if st.button("🔍 BUSCAR SEDES", key="btn_buscar"):
        if n_est:
            with st.spinner(f"Consultando disponibilidad para {n_est}..."):
                try:
                    # Consulta a la tabla que creaste
                    query = supabase.table("sedes_clinicas").select("*").ilike("estudio", f"%{n_est}%").execute()
                    
                    if query.data:
                        df_res = pd.DataFrame(query.data)
                        # Estandarizamos nombres para la visualización
                        df_res = df_res.rename(columns={
                            "nombre": "Nombre",
                            "precio": "Precio",
                            "whatsapp": "Whatsapp",
                            "ciudad": "Ciudad"
                        })
                        st.session_state.final_df = df_res.sort_values("Precio")
                        st.session_state.n_est = n_est
                        st.rerun()
                    else:
                        st.warning(f"No encontramos resultados para '{n_est}'. Intenta con otro nombre.")
                except Exception as e:
                    st.error(f"Error de conexión con la base de datos: {e}")
        else:
            st.warning("Por favor, escribe el nombre de un estudio.")

    # --- MOSTRAR RESULTADOS ---
    if 'final_df' in st.session_state:
        df = st.session_state.final_df
        mejor = df.iloc[0] # La opción más barata
        
        st.markdown("---")
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.markdown(f"""
            <div class="card">
                <h3 style='color: #1a73e8;'>✨ Opción más Recomendada</h3>
                <h2 style='margin: 0;'>${mejor['Precio']}</h2>
                <p><b>Clínica:</b> {mejor['Nombre']}<br>
                <b>Zona:</b> {mejor['Ciudad']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            
            # Datos de contacto y mapa
            wa_num = mejor['Whatsapp']
            lat_v = mejor.get('lat', 10.48)
            lon_v = mejor.get('lon', -66.90)
            
            # Botones de acción
            st.markdown(f'''
                <a href="https://wa.me/{wa_num}?text=Hola,%20deseo%20agendar%20un%20{st.session_state.n_est}" target="_blank" style="text-decoration:none;">
                    <div style="background-color:#25D366; color:white; padding:12px; border-radius:10px; text-align:center; font-weight:bold; margin-bottom:10px;">📱 CONTACTAR POR WHATSAPP</div>
                </a>
                <a href="https://www.google.com/maps/search/?api=1&query={lat_v},{lon_v}" target="_blank" style="text-decoration:none;">
                    <div style="background-color:#4285F4; color:white; padding:12px; border-radius:10px; text-align:center; font-weight:bold;">📍 VER EN GOOGLE MAPS</div>
                </a>
            ''', unsafe_allow_html=True)

        with c2:
            st.subheader("Ubicación en el Mapa")
            m = folium.Map(location=[lat_v, lon_v], zoom_start=15)
            folium.Marker(
                [lat_v, lon_v], 
                popup=mejor['Nombre'],
                tooltip=mejor['Nombre'],
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)
            folium_static(m, width=450, height=350)

# ==========================================
# --- 2. SECCIÓN ADMINISTRADOR (GESTIÓN) ---
# ==========================================
elif st.session_state.perfil == 'admin':
    st.title("⚙️ Panel de Gestión de Sedes")
    
    # Aquí puedes agregar el código para insertar nuevas sedes a Supabase
    with st.expander("➕ Registrar Nueva Sede/Estudio"):
        with st.form("nueva_sede"):
            f_nom = st.text_input("Nombre de la Clínica")
            f_est = st.text_input("Nombre del Estudio")
            f_pre = st.number_input("Precio ($)", min_value=0)
            f_cit = st.text_input("Ciudad/Zona")
            f_lat = st.number_input("Latitud", format="%.6f")
            f_lon = st.number_input("Longitud", format="%.6f")
            f_wha = st.text_input("WhatsApp (ej: 584121234567)")
            
            if st.form_submit_button("Guardar en Supabase"):
                try:
                    data = {
                        "nombre": f_nom, "estudio": f_est, "precio": f_pre,
                        "ciudad": f_cit, "lat": f_lat, "lon": f_lon, "whatsapp": f_wha
                    }
                    supabase.table("sedes_clinicas").insert(data).execute()
                    st.success("✅ Sede registrada exitosamente.")
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    st.write("Consulta la tabla actual en Supabase para verificar los datos.")
