import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import os
import unicodedata
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. Función para normalizar texto (acentos y mayúsculas)
def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

st.set_page_config(page_title="Buscador Médico Pro", page_icon="🩺")
st.title("🩺 Buscador Médico Inteligente")

# Barra lateral
with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Ingresa tu Gemini API Key:", type="password")
    user_city = st.text_input("📍 Tu ubicación (Ciudad, País):", "Valencia, Venezuela")
    st.info("💡 Buscaremos el mejor precio y la clínica más cercana.")

st.header("1. Sube la foto de la Orden Médica")
uploaded_image = st.file_uploader("Captura o selecciona la imagen", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar Mejor Opción"):
    if not api_key_user or not uploaded_image:
        st.error("⚠️ Falta la API Key o la imagen.")
    else:
        try:
            nombre_archivo = "base_clinicas.xlsx"
            if not os.path.exists(nombre_archivo):
                st.error("❌ No encontré el archivo Excel en GitHub.")
            else:
                # Cargar y limpiar base de datos
                df = pd.read_excel(nombre_archivo)
                df.columns = df.columns.str.strip().str.capitalize()

                # Analizar imagen con IA
                genai.configure(api_key=api_key_user)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                
                with st.spinner('IA Analizando estudio...'):
                    prompt = "Identify the medical study. Respond ONLY with the name of the study found in the image in Spanish."
                    response = model.generate_content([prompt, img])
                    detectado = response.text.strip()
                
                st.success(f"Estudio detectado: **{detectado}**")
                
                # Búsqueda con normalización de acentos
                detectado_limpio = normalizar_texto(detectado)
                resultados = df[df['Estudio'].apply(normalizar_texto).str.contains(detectado_limpio, na=False)].copy()
                
                if not resultados.empty:
                    # Calcular distancias si hay ubicación
                    geolocator = Nominatim(user_agent="medical_app_v1")
                    user_loc = geolocator.geocode(user_city)
                    
                    def obtener_distancia(row):
                        try:
                            loc = geolocator.geocode(row['Direccion'])
                            if loc and user_loc:
                                return round(geodesic((user_loc.latitude, user_loc.longitude), (loc.latitude, loc.longitude)).km, 1)
                        except: pass
                        return None

                    with st.spinner('Calculando distancias...'):
                        resultados['Km'] = resultados.apply(obtener_distancia, axis=1)
                    
                    # Ordenar por precio
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.sort_values(by='Precio')
                    
                    mejor = resultados.iloc[0]
                    st.balloons()
                    
                    # Mostrar Recomendación
                    st.subheader(f"🌟 Recomendación: {mejor['Nombre']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="Precio", value=f"${int(mejor['Precio'])}")
                        st.write(f"📍 **Dirección:** {mejor.get('Direccion', 'No disponible')}")
                    with col2:
                        dist = mejor.get('Km')
                        if dist is not None:
                            st.metric(label="Distancia", value=f"{dist} Km")
                        
                        if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                            num = str(int(mejor['Whatsapp']))
                            st.markdown(f"[💬 Contactar por WhatsApp](https://wa.me/{num})")

                    st.write("---")
                    st.write("### 📍 Todas las opciones encontradas:")
                    st.dataframe(resultados[['Nombre', 'Precio', 'Km', 'Direccion']], use_container_width=True)
                else:
                    st.warning(f"No hay convenios para '{detectado}'.")
                    
        except Exception as e:
            st.error(f"Ocurrió un error: {e}")
