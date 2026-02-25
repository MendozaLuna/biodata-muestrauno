# --- 5. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"):
        st.session_state.perfil = None
        st.rerun()

    st.title("🔍 Buscador de Estudios")

    # --- NUEVA ESTRATEGIA DE UBICACIÓN ---
    st.markdown("### 📍 ¿Dónde te encuentras?")
    
    # Creamos dos columnas: una para el GPS y otra para el texto manual
    col_gps, col_manual = st.columns([1, 2])
    
    with col_gps:
        # El botón de JS Eval que dispara la acción real del navegador
        # Usamos una versión más directa de la función
        loc_json = streamlit_js_eval(
            data_string="navigator.geolocation.getCurrentPosition", 
            want_output=True, 
            key="get_pos"
        )
        st.write("Pulsa para activar GPS:")

    u_lat, u_lon = None, None
    
    # Verificamos si el JS devolvió coordenadas
    if loc_json and 'coords' in loc_json:
        u_lat = loc_json['coords']['latitude']
        u_lon = loc_json['coords']['longitude']
        st.success("✅ GPS Activado")
        u_city = "Ubicación por GPS"
    else:
        with col_manual:
            u_city = st.text_input("O escribe tu ciudad manualmente:", "Caracas, Venezuela")

    st.write("---")
    
    # (El resto del código del buscador sigue aquí abajo)
    c_op1, c_op2 = st.columns(2)
    with c_op1: prio = st.radio("Ordenar por:", ("Precio", "Ubicación"), horizontal=True)
    with c_op2: manual = st.text_input("⌨️ ¿Qué examen buscas?", placeholder="Ej: OCT, Campimetría...")

    up_img = st.file_uploader("Sube foto de la orden", type=["jpg", "jpeg", "png"])
