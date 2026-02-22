import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import os

st.set_page_config(page_title="Buscador de Convenios Médicos", page_icon="🩺")
st.title("🩺 Buscador de Convenios con IA")

# Configuración en la barra lateral
with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Ingresa tu Gemini API Key:", type="password")
    st.info("💡 El archivo de clínicas ya está cargado en el sistema.")

st.header("1. Sube la foto de la Orden Médica")
uploaded_image = st.file_uploader("Captura o selecciona la imagen", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar Mejor Precio"):
    if not api_key_user or not uploaded_image:
        st.error("⚠️ Falta la API Key o la imagen de la orden.")
    else:
        try:
            # 1. Cargar la base de datos automáticamente
            nombre_archivo = "base_clinicas.xlsx"
            if not os.path.exists(nombre_archivo):
                st.error(f"❌ No encontré el archivo '{nombre_archivo}' en GitHub. Asegúrate de subirlo.")
            else:
                df = pd.read_excel(nombre_archivo)
                df.columns = df.columns.str.strip().str.capitalize()

                # 2. Configurar IA
                genai.configure(api_key=api_key_user)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                
                with st.spinner('IA Analizando orden...'):
                    prompt = "Identify the medical study. Respond ONLY with the name of the study found in the image in Spanish."
                    response = model.generate_content([prompt, img])
                    detectado = response.text.strip()
                
                st.success(f"Estudio detectado: *{detectado}*")
                
                # 3. Buscar en la base cargada
                if 'Estudio' in df.columns and 'Precio' in df.columns:
                    resultados = df[df['Estudio'].str.contains(detectado, case=False, na=False)].copy()
                    
                    if not resultados.empty:
                        resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                        resultados = resultados.dropna(subset=['Precio']).sort_values(by='Precio')
                        
                        mejor = resultados.iloc[0]
                        st.balloons()
                        st.metric(label="🌟 Opción más económica", value=str(mejor.get('Nombre', 'Clínica')), delta=f"${mejor['Precio']}")
                        st.write("### 📍 Comparativa de precios:")
                        st.dataframe(resultados, use_container_width=True)
                    else:
                        st.warning(f"No hay convenios registrados para '{detectado}'.")
                else:
                    st.error("El Excel en GitHub no tiene las columnas 'Estudio' y 'Precio'.")
                
        except Exception as e:
            st.error(f"Error: {e}")
