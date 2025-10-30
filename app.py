import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(
    page_title="RSI en USD - Acciones Argentinas",
    page_icon="📈",
    layout="wide"
)

# Título
st.title("📈 RSI en Dólares - Acciones Argentinas")
st.markdown("Calcula el RSI de acciones argentinas expresado en dólares usando el tipo de cambio implícito de GGAL")

# Función para obtener tipo de cambio
@st.cache_data(ttl=300)  # Cache por 5 minutos
def obtener_tipo_cambio():
    """
    Calcula el tipo de cambio usando el ratio GGAL
    GGAL.BA / GGAL (NASDAQ) * 10
    """
    try:
        # GGAL en Buenos Aires
        ggal_ba = yf.Ticker("GGAL.BA")
        precio_ba = ggal_ba.history(period="1d")['Close'].iloc[-1]
        
        # GGAL en NASDAQ
        ggal_us = yf.Ticker("GGAL")
        precio_us = ggal_us.history(period="1d")['Close'].iloc[-1]
        
        # Calcular tipo de cambio
        tipo_cambio = (precio_ba / precio_us) * 10
        
        return tipo_cambio, precio_ba, precio_us
        
    except Exception as e:
        st.error(f"Error obteniendo tipo de cambio: {e}")
        return None, None, None

# Función para calcular RSI
def calcular_rsi(precios, periodo=14):
    """
    Calcula el RSI (Relative Strength Index)
    """
    deltas = precios.diff()
    ganancias = deltas.where(deltas > 0, 0)
    perdidas = -deltas.where(deltas < 0, 0)
    
    avg_ganancias = ganancias.rolling(window=periodo).mean()
    avg_perdidas = perdidas.rolling(window=periodo).mean()
    
    rs = avg_ganancias / avg_perdidas
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

# Función para obtener datos de una acción
@st.cache_data(ttl=300)
def obtener_datos_accion(ticker, periodo_dias=90):
    """
    Obtiene datos históricos de una acción argentina
    """
    try:
        # Intentar con .BA (Buenos Aires)
        ticker_ba = f"{ticker}.BA"
        stock = yf.Ticker(ticker_ba)
        
        # Obtener datos históricos
        end_date = datetime.now()
        start_date = end_date - timedelta(days=periodo_dias)
        
        df = stock.history(start=start_date, end=end_date)
        
        if df.empty:
            return None, None
        
        return df, ticker_ba
        
    except Exception as e:
        st.error(f"Error obteniendo datos de {ticker}: {e}")
        return None, None

# Función principal de análisis
def analizar_accion(ticker, tipo_cambio, periodo_rsi=14):
    """
    Analiza una acción y retorna sus métricas
    """
    df, ticker_completo = obtener_datos_accion(ticker)
    
    if df is None or df.empty:
        return None
    
    # Calcular RSI en ARS
    df['RSI'] = calcular_rsi(df['Close'], periodo_rsi)
    
    # Precio actual
    precio_ars = df['Close'].iloc[-1]
    precio_usd = precio_ars / tipo_cambio
    
    # RSI actual
    rsi_actual = df['RSI'].iloc[-1]
    
    # Retornar resultados
    return {
        'ticker': ticker,
        'ticker_completo': ticker_completo,
        'precio_ars': precio_ars,
        'precio_usd': precio_usd,
        'rsi': rsi_actual,
        'df': df
    }

# Sidebar con configuración
st.sidebar.header("⚙️ Configuración")

# Período RSI
periodo_rsi = st.sidebar.slider(
    "Período RSI",
    min_value=7,
    max_value=30,
    value=14,
    help="Cantidad de períodos para calcular el RSI"
)

# Período histórico
periodo_dias = st.sidebar.slider(
    "Días históricos",
    min_value=30,
    max_value=365,
    value=90,
    help="Cantidad de días de historia a analizar"
)

# Lista de tickers predefinidos
st.sidebar.header("📋 Acciones Predefinidas")
tickers_predefinidos = ["GGAL", "YPF", "BBAR", "BMA", "CEPU", "EDN", "LOMA", "PAM", "YPFD", "TXAR"]

usar_predefinidos = st.sidebar.checkbox("Usar lista predefinida", value=True)

if usar_predefinidos:
    tickers_seleccionados = st.sidebar.multiselect(
        "Selecciona acciones:",
        tickers_predefinidos,
        default=["GGAL", "YPF", "BBAR"]
    )
else:
    # Input manual
    st.sidebar.markdown("**Ingresar tickers manualmente:**")
    tickers_input = st.sidebar.text_area(
        "Un ticker por línea:",
        "HAVA\nBYMA\nMOLA",
        height=150
    )
    tickers_seleccionados = [t.strip() for t in tickers_input.split('\n') if t.strip()]

# Sección principal
col1, col2 = st.columns([2, 1])

with col1:
    st.header("💵 Tipo de Cambio Implícito")
    
    # Botón para actualizar TC
    if st.button("🔄 Actualizar Tipo de Cambio", type="secondary"):
        st.cache_data.clear()
    
    # Obtener tipo de cambio
    with st.spinner("Obteniendo tipo de cambio..."):
        tc, precio_ba, precio_us = obtener_tipo_cambio()
    
    if tc:
        st.success(f"**Tipo de Cambio: ${tc:.2f}**")
        st.caption(f"GGAL.BA: ${precio_ba:.2f} | GGAL (NASDAQ): USD ${precio_us:.2f}")
    else:
        st.error("No se pudo obtener el tipo de cambio")
        st.stop()

with col2:
    st.metric("📊 Período RSI", periodo_rsi)
    st.metric("📅 Días Históricos", periodo_dias)

# Separador
st.divider()

# Sección de cálculo
st.header("🎯 Calcular RSI")

if st.button("🚀 CALCULAR RSI DE TODAS LAS ACCIONES", type="primary", use_container_width=True):
    
    if not tickers_seleccionados:
        st.warning("⚠️ No hay acciones seleccionadas")
        st.stop()
    
    # Crear contenedor para resultados
    resultados = []
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Procesar cada ticker
    for idx, ticker in enumerate(tickers_seleccionados):
        status_text.text(f"Procesando {ticker}... ({idx + 1}/{len(tickers_seleccionados)})")
        
        resultado = analizar_accion(ticker, tc, periodo_rsi)
        
        if resultado:
            resultados.append(resultado)
        
        # Actualizar progress bar
        progress_bar.progress((idx + 1) / len(tickers_seleccionados))
    
    # Limpiar status
    status_text.empty()
    progress_bar.empty()
    
    # Mostrar resultados
    if resultados:
        st.success(f"✅ Se procesaron {len(resultados)} acciones correctamente")
        
        # Crear DataFrame con resultados
        df_resultados = pd.DataFrame([
            {
                'Ticker': r['ticker'],
                'Precio ARS': f"${r['precio_ars']:.2f}",
                'Precio USD': f"${r['precio_usd']:.2f}",
                'RSI': f"{r['rsi']:.2f}",
                'Señal': '🟢 Sobreventa' if r['rsi'] < 30 else ('🔴 Sobrecompra' if r['rsi'] > 70 else '🟡 Neutral')
            }
            for r in resultados
        ])
        
        # Mostrar tabla
        st.dataframe(
            df_resultados,
            use_container_width=True,
            hide_index=True
        )
        
        # Descargar CSV
        csv = df_resultados.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar resultados (CSV)",
            data=csv,
            file_name=f"rsi_acciones_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
        # Gráficos individuales
        st.divider()
        st.header("📊 Gráficos Detallados")
        
        # Selector de acción para graficar
        ticker_graficar = st.selectbox(
            "Selecciona una acción para ver detalle:",
            [r['ticker'] for r in resultados]
        )
        
        # Encontrar resultado seleccionado
        resultado_sel = next(r for r in resultados if r['ticker'] == ticker_graficar)
        df_grafico = resultado_sel['df']
        
        # Crear gráfico con Plotly
        fig = go.Figure()
        
        # Subplot 1: Precio
        fig.add_trace(go.Scatter(
            x=df_grafico.index,
            y=df_grafico['Close'],
            name='Precio (ARS)',
            line=dict(color='blue', width=2)
        ))
        
        # Subplot 2: RSI
        fig.add_trace(go.Scatter(
            x=df_grafico.index,
            y=df_grafico['RSI'],
            name='RSI',
            line=dict(color='purple', width=2),
            yaxis='y2'
        ))
        
        # Líneas de referencia RSI
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, yref='y2')
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, yref='y2')
        
        # Layout
        fig.update_layout(
            title=f"{ticker_graficar} - Precio y RSI",
            xaxis_title="Fecha",
            yaxis=dict(title="Precio (ARS)", side='left'),
            yaxis2=dict(title="RSI", side='right', overlaying='y', range=[0, 100]),
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Métricas adicionales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Precio Actual (ARS)", f"${resultado_sel['precio_ars']:.2f}")
        
        with col2:
            st.metric("Precio Actual (USD)", f"${resultado_sel['precio_usd']:.2f}")
        
        with col3:
            st.metric("RSI Actual", f"{resultado_sel['rsi']:.2f}")
        
        with col4:
            variacion = ((df_grafico['Close'].iloc[-1] / df_grafico['Close'].iloc[0]) - 1) * 100
            st.metric("Variación (%)", f"{variacion:.2f}%")
    
    else:
        st.error("❌ No se pudieron procesar las acciones")

# Footer
st.divider()
st.caption("💡 **Nota**: El RSI es un indicador técnico. Valores < 30 indican sobreventa, > 70 sobrecompra.")
st.caption(f"🕒 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
