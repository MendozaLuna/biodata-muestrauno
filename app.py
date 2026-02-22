import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
import os

st.set_page_config(page_title="Buscador Médico Pro", page_icon="🩺")
st.title("🩺 Buscador de Convenios con IA")

with st.sidebar:
    st.header("Configuración")
    api_key_user = st.text_input("Ingresa tu Gemini API Key:", type="password")
    st.info("💡 Base de datos de centros conectada.")

st.header("1. Sube la foto de la Orden Médica")
uploaded_image = st.file_uploader("Captura o selecciona la imagen", type=["jpg", "jpeg", "png"])

if st.button("🔍 Buscar Mejor Precio y Contacto"):
    if not api_key_user or not uploaded_image:
        st.error("⚠️ Falta la API Key o la imagen.")
    else:
        try:
            nombre_archivo = "base_clinicas.xlsx"
            if not os.path.exists(nombre_archivo):
                st.error("❌ No encontré el archivo Excel en GitHub.")
            else:
                df = pd.read_excel(nombre_archivo)
                df.columns = df.columns.str.strip().str.capitalize()

                genai.configure(api_key=api_key_user)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                img = PIL.Image.open(uploaded_image)
                
                with st.spinner('IA Analizando...'):
                    prompt = "Identify the medical study. Respond ONLY with the name of the study found in the image in Spanish."
                    response = model.generate_content([prompt, img])
                    detectado = response.text.strip()
                
                st.success(f"Estudio detectado: *{detectado}*")
                
                if 'Estudio' in df.columns:
                    resultados = df[df['Estudio'].str.contains(detectado, case=False, na=False)].copy()
                    
                    if not resultados.empty:
                        resultados['Precio'] = pd.to_numeric(resultados['Precio'], errors='coerce')
                        resultados = resultados.dropna(subset=['Precio']).sort_values(by='Precio')
                        
                        mejor = resultados.iloc[0]
                        st.balloons()
                        
                        # --- DISEÑO DE LA MEJOR OPCIÓN ---
                        st.subheader(f"🌟 Mejor Opción: {mejor['Nombre']}")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric(label="Precio", value=f"${mejor['Precio']}")
                            if 'Dirección' in mejor:
                                st.write(f"📍 *Dirección:* {mejor['Dirección']}")
                        
                        with col2:
                            if 'Whatsapp' in mejor and pd.notna(mejor['Whatsapp']):
                                # Crea un link directo a WhatsApp
                                ws_link = f"https://wa.me/{mejor['Whatsapp']}"
                                st.markdown(f"[💬 Contactar por WhatsApp]({ws_link})")
                            if 'Redes' in mejor and pd.notna(mejor['Redes']):
                                st.write(f"📱 *Redes:* {mejor['Redes']}")
                        
                        st.write("---")
                        st.write("### 📍 Comparativa completa:")
                        st.dataframe(resultados, use_container_width=True)
                    else:
                        st.warning(f"No hay convenios para '{detectado}'.")
        except Exception as e:
            st.error(f"Error: {e}")
