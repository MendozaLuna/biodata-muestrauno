# --- BLOQUE DE UBICACIÓN OPTIMIZADO ---
    st.markdown("### 📍 ¿Dónde te encuentras?")
    
    if 'activar_gps' not in st.session_state:
        st.session_state.activar_gps = False

    col_btn, col_txt = st.columns([1, 2])

    with col_btn:
        if st.button("🎯 USAR MI GPS ACTUAL"):
            st.session_state.activar_gps = True

    u_lat, u_lon = None, None
    u_city = "Caracas, Venezuela" 

    if st.session_state.activar_gps:
        # Intentamos obtener la ubicación
        loc_json = streamlit_js_eval(data_string="navigator.geolocation.getCurrentPosition", want_output=True, key="get_pos")
        
        if loc_json and 'coords' in loc_json:
            u_lat = loc_json['coords']['latitude']
            u_lon = loc_json['coords']['longitude']
            st.success("✅ GPS Activado")
            u_city = "Ubicación GPS"
        else:
            # Si después de intentar no hay respuesta, mostramos un mensaje más sutil
            st.info("📡 Buscando señal GPS... Si no aparece el permiso, escribe tu ciudad a la derecha.")

    # Siempre mostramos el campo manual como respaldo
    with col_txt:
        u_city = st.text_input("O escribe tu ciudad manualmente:", u_city if u_lat else "Caracas, Venezuela")
