import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
from PIL import Image

st.set_page_config(page_title="Control Súper 21€", page_icon="🛒", layout="centered")

st.title("🛒 Asistente de Compra Diaria")

# Cargar catálogo desde el Excel
@st.cache_data
def cargar_datos():
    df_cat = pd.read_excel("transcripcion_tickets_supermercado.xlsx", sheet_name="Catálogo Maestro Productos")
    return df_cat

try:
    df_catalogo = cargar_datos()
except Exception as e:
    st.error(f"Error al leer el archivo Excel: {e}")
    st.stop()

# Menú superior
pestana1, pestana2, pestana3 = st.tabs(["📸 Escanear Carro", "📋 Plan de Hoy (~21€)", "📦 Catálogo de Precios"])

# ==================== PESTAÑA 1: FOTO DEL CARRO ====================
with pestana1:
    st.subheader("Calcula el total de tu carro por foto")
    
    api_key = st.text_input("Introduce tu clave API de Gemini:", type="password", help="Obtenida gratis en AI Studio")
    
    archivo_foto = st.camera_input("Toma una foto al interior del carro")
    if not archivo_foto:
        archivo_foto = st.file_uploader("O sube una foto desde la galería", type=["jpg", "jpeg", "png"])
        
    if archivo_foto and st.button("Analizar e Importe Aproximado", type="primary"):
        if not api_key:
            st.warning("Por favor, introduce tu clave API arriba para poder procesar la imagen.")
        else:
            with st.spinner("Analizando artículos y cruzando con tu catálogo..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    
                    imagen = Image.open(archivo_foto)
                    
                    # Convertir catálogo a texto plano para el prompt
                    catalogo_resumen = df_catalogo[["Artículo", "Descripción / Tipo", "Precio Ref. (€)"]].to_dict(orient="records")
                    
                    prompt = f"""
                    Eres un asistente de compras. Identifica todos los artículos visibles en esta foto de un carro de supermercado.
                    Cruza los artículos con este catálogo de referencia de este supermercado:
                    {json.dumps(catalogo_resumen, ensure_ascii=False)}
                    
                    Devuelve EXCLUSIVAMENTE un JSON válido con este formato, sin bloques de código Markdown ni texto adicional:
                    {{
                        "articulos": [
                            {{"nombre": "Nombre del producto", "cantidad": 1, "precio_unitario": 1.25, "total": 1.25}}
                        ],
                        "total_aproximado": 0.00
                    }}
                    """
                    
                    respuesta = model.generate_content([prompt, imagen])
                    texto_limpio = respuesta.text.replace("```json", "").replace("```", "").strip()
                    resultado = json.loads(texto_limpio)
                    
                    total = resultado.get("total_aproximado", 0.0)
                    
                    st.metric(label="Total Estimado en el Carro", value=f"{total:.2f} €")
                    
                    if total <= 20.0:
                        st.success(f"Cubierto totalmente con la tarjeta (te sobran {(20.0 - total):.2f} €).")
                    elif total <= 23.0:
                        st.warning(f"Usas los 20 € de tarjeta + pagas {(total - 20.0):.2f} € en efectivo.")
                    else:
                        st.error(f"¡Atención! Te pasas del límite de 23 € en {(total - 23.0):.2f} €.")
                    
                    st.write("### Artículos Detectados:")
                    df_detectados = pd.DataFrame(resultado.get("articulos", []))
                    if not df_detectados.empty:
                        st.dataframe(df_detectados, use_container_width=True)
                        
                except Exception as err:
                    st.error(f"Error procesando la imagen: {err}")

# ==================== PESTAÑA 2: PLANIFICADOR DIARIO ====================
with pestana2:
    st.subheader("Reparto mensual en compras de ~21 €")
    st.write("Genera combinaciones para consumir todo tu stock mensual sin exceder tu límite diario.")
    
    meta_gasto = st.slider("Objetivo por día (€):", min_value=18.0, max_value=23.0, value=21.0, step=0.5)
    
    if st.button("Calcular Plan Diario de Compra"):
        articulos_pendientes = []
        for _, row in df_catalogo.iterrows():
            c = max(1, int(round(row["Cantidad Total"])))
            for _ in range(c):
                articulos_pendientes.append({
                    "Artículo": row["Artículo"],
                    "Precio": float(row["Precio Ref. (€)"])
                })
        
        articulos_pendientes.sort(key=lambda x: x["Precio"], reverse=True)
        
        dias = []
        while articulos_pendientes:
            cesta = []
            gasto = 0.0
            restantes = []
            for item in articulos_pendientes:
                if gasto + item["Precio"] <= meta_gasto + 1.5:  # Margen hasta 22.5 - 23 €
                    cesta.append(item)
                    gasto += item["Precio"]
                else:
                    restantes.append(item)
            
            dias.append({"articulos": cesta, "total": round(gasto, 2)})
            articulos_pendientes = restantes
        
        st.success(f"Tu compra mensual se reparte en {len(dias)} días de compra óptimos.")
        
        for i, d in enumerate(dias, start=1):
            with st.expander(f"Día {i} — Total: {d['total']:.2f} €"):
                for it in d["articulos"]:
                    st.write(f"• **{it['Artículo']}** — {it['Precio']:.2f} €")

# ==================== PESTAÑA 3: CATÁLOGO ====================
with pestana3:
    st.subheader("Precios de referencia extraídos de tus tickets")
    filtro = st.text_input("Buscar producto:")
    df_filtrado = df_catalogo.copy()
    if filtro:
        df_filtrado = df_filtrado[df_filtrado["Artículo"].str.contains(filtro, case=False, na=False)]
    st.dataframe(df_filtrado[["Artículo", "Categoría", "Precio Ref. (€)", "Veces Comprado"]], use_container_width=True)
