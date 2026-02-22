import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os

# ... (mantener funciones de IA y normalización anteriores) ...

st.title("🩺 Buscador Médico Inteligente (Precio + Distancia)")

# 1. Función para obtener ubicación (Simulada para Streamlit Cloud básico)
# Nota: Para GPS real se usa streamlit-js-eval, aquí usaremos una entrada de ciudad por ahora
user_city = st.sidebar.text_input("📍 Tu ubicación actual (Ciudad/Barrio):", "Valencia, Venezuela")

# ... (resto del proceso de IA) ...

if not resultados.empty:
    geolocator = Nominatim(user_agent="medical_app")
    user_loc = geolocator.geocode(user_city)
    
    if user_loc:
        def calcular_km(row):
            try:
                # Busca la dirección de la clínica en el mapa
                clinica_loc = geolocator.geocode(row['Dirección'])
                if clinica_loc:
                    return geodesic((user_loc.latitude, user_loc.longitude), 
                                   (clinica_loc.latitude, clinica_loc.longitude)).km
                return 999 # Si no encuentra la dirección
            except:
                return 999

        with st.spinner('Calculando distancias...'):
            resultados['Distancia (Km)'] = resultados.apply(calcular_km, axis=1)
            
        # Ordenar por precio, pero mostrar la distancia
        resultados = resultados.sort_values(by='Precio')
        
        mejor = resultados.iloc[0]
        st.success(f"🌟 Recomendación: {mejor['Nombre']} es el más barato y está a {mejor['Distancia (Km)']:.1f} km de ti.")
