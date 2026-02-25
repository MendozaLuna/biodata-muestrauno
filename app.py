# --- 5. CONTENIDO PACIENTE ---
if st.session_state.perfil == 'persona':
    if st.button("⬅️ Volver", key="v_p"):
        st.session_state.perfil = None; st.rerun()

    # --- SOLICITUD DE UBICACIÓN CORREGIDA ---
    st.markdown("### 📍 Configuración de Ubicación")
    
    # Intentamos obtener la ubicación mediante JS
    # Si el usuario ya dio permiso, 'loc' tendrá datos. Si no, lanzará la pregunta.
    loc = streamlit_js_eval(data_string="navigator.geolocation", want_output=True, key="get_location")
    
    u_lat, u_lon = None, None
    
    # Verificamos si la respuesta de JS tiene las coordenadas
    if isinstance(loc, dict) and 'coords' in loc:
        u_lat = loc['coords']['latitude']
        u_lon = loc['coords']['longitude']
        st.success(f"✅ Ubicación detectada con éxito")
    else:
        st.info("💡 Por favor, acepta el permiso de ubicación en tu navegador para calcular distancias exactas. Si prefieres no hacerlo, puedes escribir tu ciudad abajo.")

    # --- LÓGICA DEL BUSCADOR ---
    def registrar_clic_real(clinica, estudio):
        try:
            data = {"clinica": clinica, "estudio": estudio, "fecha": datetime.now().isoformat()}
            supabase.table("clics").insert(data).execute()
        except: pass 

    def calcular_distancia(lat1, lon1, lat2, lon2):
        try:
            R = 6371.0 
            dlat = math.radians(float(lat2) - float(lat1))
            dlon = math.radians(float(lon2) - float(lon1))
            a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return round(R * c, 1)
        except: return 99.0

    st.title("🔍 Buscador de Estudios")
    
    # Si tenemos coordenadas GPS, ocultamos el input de ciudad o lo ponemos como opcional
    if u_lat and u_lon:
        u_city = "GPS Activo"
        st.write(f"🌍 Distancias calculadas desde tu posición actual.")
    else:
        u_city = st.text_input("📍 Tu ubicación actual (Ciudad):", "Caracas, Venezuela")
