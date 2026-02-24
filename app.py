import streamlit as st
import google.generativeai as genai
import pandas as pd
import PIL.Image
from supabase import create_client, Client # Librería nueva
from datetime import datetime

# --- 1. CONFIGURACIÓN DE SEGURIDAD Y BASES DE DATOS ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Configura las llaves en los Secrets.")
    st.stop()

# Conexión a Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def registrar_clic_real(clinica, estudio):
    """Guarda el clic en la base de datos de Supabase"""
    try:
        data = {
            "clinica": clinica,
            "estudio": estudio,
            "fecha": datetime.now().isoformat()
        }
        supabase.table("clicks").insert(data).execute()
    except Exception as e:
        print(f"Error guardando en BD: {e}")

# ... (El resto del código de estilo y funciones de distancia se mantiene igual) ...

# --- DENTRO DEL BOTÓN DE WHATSAPP ---
if 'Whatsapp' in mejor:
    wa = str(mejor['Whatsapp']).split('.')[0]
    url_c = f"https://wa.me/{wa}?text=Hola,%20vengo%20de%20BioData.%20Deseo%20cita%20para:%20{nombre_estudio}"
    
    # Este botón ahora guarda el dato en la nube antes de ir a WhatsApp
    if st.button(f"💬 AGENDAR EN {mejor['Nombre']}"):
        registrar_clic_real(mejor['Nombre'], nombre_estudio)
        st.markdown(f'<meta http-equiv="refresh" content="0;URL={url_c}">', unsafe_allow_html=True)
        st.write("Registrando interés y redirigiendo...")

# --- PANEL DE ADMINISTRADOR CON DATOS REALES ---
st.write("---")
if st.checkbox("📊 Ver Estadísticas Reales (Admin)"):
    # Consultamos la base de datos en tiempo real
    response = supabase.table("clicks").select("*").execute()
    df_clicks = pd.DataFrame(response.data)
    
    if not df_clicks.empty:
        st.success(f"BioData ha generado {len(df_clicks)} derivaciones en total.")
        # Mostramos cuántos clics tiene cada clínica
        stats = df_clicks['clinica'].value_counts()
        st.bar_chart(stats)
    else:
        st.info("Aún no hay clics registrados en la base de datos.")
