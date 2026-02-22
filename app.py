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
uploaded_excel = st.file_uploader("Sube tu archivo 'base_clinicas.xlsx'", type=["xlsx"])
uploaded_image = st.file_uploader("2. Sube la foto de la Orden Médica", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar Mejor Precio"):
    if not api_key_user or not uploaded_excel or not uploaded_image:
        st.error("⚠️ Falta información para procesar.")
    else:
        try:
            genai.configure(api_key=api_key_user)
            model = genai.GenerativeModel('models/gemini-1.5-flash')
            df = pd.read_excel(uploaded_excel)
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            img = PIL.Image.open(uploaded_image)
            
            with st.spinner('Analizando...'):
                prompt = "Identify the medical study. Respond ONLY with: 'Oct Nervio optico' or 'Topografía' or 'Paquimetria'."
                response = model.generate_content([prompt, img])
                detectado = response.text.strip()
            
            st.success(f"Estudio detectado: *{detectado}*")
            resultados = df[df['Estudio'].str.contains(detectado, case=False, na=False)].copy()
            
            if not resultados.empty:
                resultados['Precio'] = pd.to_numeric(resultados['Precio'])
                resultados = resultados.sort_values(by='Precio')
                mejor = resultados.iloc[0]
                st.balloons()
                st.metric(label="🌟 Opción Recomendada", value=mejor['Nombre'], delta=f"${mejor['Precio']}")
                st.dataframe(resultados[['Nombre', 'Precio', 'Estudio']], use_container_width=True)
            else:
                st.warning(f"No encontré coincidencias para '{detectado}'.")
        except Exception as e:
            st.error(f"Error: {e}")
