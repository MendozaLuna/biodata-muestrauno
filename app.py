import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image

st.set_page_config(page_title="Buscador de Convenios Médicos", page_icon="🩺")
st.title("🩺 Buscador de Convenios con IA")

with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Ingresa tu Gemini API Key:", type="password")

st.header("1. Carga de Datos")
uploaded_excel = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])
uploaded_image = st.file_uploader("2. Sube la foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar Mejor Precio"):
    if not api_key_user or not uploaded_excel or not uploaded_image:
        st.error("⚠️ Falta información (API Key, Excel o Imagen).")
    else:
        try:
            genai.configure(api_key=api_key_user)
            model = genai.GenerativeModel('models/gemini-flash-latest')
            
            # Leer Excel y limpiar nombres de columnas
            df = pd.read_excel(uploaded_excel)
            df.columns = df.columns.str.strip().str.capitalize() # Convierte "precio " en "Precio"
            
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('IA Analizando estudio...'):
                prompt = "Identify the medical study. Respond ONLY with the name of the study found in the image in Spanish."
                response = model.generate_content([prompt, img])
                detectado = response.text.strip()
            
            st.success(f"Estudio detectado: *{detectado}*")
            
            # Buscar el estudio en la columna 'Estudio'
            if 'Estudio' in df.columns and 'Precio' in df.columns:
                resultados = df[df['Estudio'].str.contains(detectado, case=False, na=False)].copy()
                
                if not resultados.empty:
                    resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                    resultados = resultados.dropna(subset=['Precio']).sort_values(by='Precio')
                    
                    mejor = resultados.iloc[0]
                    st.balloons()
                    st.metric(label="🌟 Opción más económica", value=str(mejor.get('Nombre', 'Clínica')), delta=f"${mejor['Precio']}")
                    st.write("### 📍 Todas las opciones:")
                    st.dataframe(resultados, use_container_width=True)
                else:
                    st.warning(f"No hay convenios para '{detectado}' en tu Excel.")
            else:
                st.error(f"Tu Excel debe tener columnas llamadas 'Estudio' y 'Precio'. Columnas detectadas: {list(df.columns)}")
                
        except Exception as e:
            st.error(f"Error: {e}")
