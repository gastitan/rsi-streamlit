import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de la página
st.set_page_config(
    page_title="RSI en USD - Acciones Argentinas",
    page_icon="📈",
    layout="wide"
)

# Título
st.title("📈 RSI en Dólares - Acciones Argentinas")
st.markdown("Calcula el RSI de acciones argentinas **expresado en dólares** usando el tipo de cambio implícito histórico de GGAL")

# Función para obtener tipo de cambio histórico
@st.cache_data(ttl=300)
def obtener_tipo_cambio_historico(periodo_dias=365):
    """
    Calcula el tipo de cambio histórico usando el ratio GGAL
    GGAL.BA / GGAL (NASDAQ) * 10
    """
    intentos = [
        ("GGAL.BA", "GGAL", 10),  # GGAL con multiplicador 10
        ("BMA.BA", "BMA", 1),      # Banco Macro sin multiplicador
        ("YPF.BA", "YPF", 1)       # YPF sin multiplicador
    ]
    
    for ticker_ba, ticker_us, multiplicador in intentos:
        try:
            st.info(f"Intentando obtener TC con {ticker_ba}/{ticker_us}...")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=periodo_dias + 30)  # Pedir más días
            
            # Descargar datos
            stock_ba = yf.download(ticker_ba, start=start_date, end=end_date, progress=False)
            stock_us = yf.download(ticker_us, start=start_date, end=end_date, progress=False)
            
            if stock_ba.empty or stock_us.empty:
                st.warning(f"No hay datos para {ticker_ba} o {ticker_us}")
                continue
            
            # Crear DataFrame con ambos precios
            df_tc = pd.DataFrame({
                'BA': stock_ba['Close'],
                'US': stock_us['Close']
            })
            
            # Eliminar NaN
            df_tc = df_tc.dropna()
            
            if len(df_tc) < 10:
                st.warning(f"Muy pocos datos para {ticker_ba}")
                continue
            
            # Calcular TC
            df_tc['TC'] = (df_tc['BA'] / df_tc['US']) * multiplicador
            
            st.success(f"✅ TC obtenido usando {ticker_ba} ({len(df_tc)} días)")
            return df_tc
            
        except Exception as e:
            st.warning(f"Error con {ticker_ba}: {str(e)}")
            continue
    
    # Si ninguno funcionó
    st.error("No se pudo obtener TC con ningún ticker. Usando TC fijo como fallback.")
    return None

# Función para obtener TC actual
@st.cache_data(ttl=300)
def obtener_tipo_cambio_actual():
    """
    Calcula el tipo de cambio actual
    """
    intentos = [
        ("GGAL.BA", "GGAL", 10),
        ("BMA.BA", "BMA", 1),
        ("YPF.BA", "YPF", 1)
    ]
    
    for ticker_ba, ticker_us, multiplicador in intentos:
        try:
            stock_ba = yf.download(ticker_ba, period="5d", progress=False)
            stock_us = yf.download(ticker_us, period="5d", progress=False)
            
            if not stock_ba.empty and not stock_us.empty:
                precio_ba = stock_ba['Close'].iloc[-1]
                precio_us = stock_us['Close'].iloc[-1]
                tipo_cambio = (precio_ba / precio_us) * multiplicador
                
                return tipo_cambio, precio_ba, precio_us
                
        except Exception as e:
            continue
    
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

# Función para obtener datos de una acción en USD
@st.cache_data(ttl=300)
def obtener_datos_accion_usd(ticker, df_tc, periodo_dias=90):
    """
    Obtiene datos históricos de una acción argentina y los convierte a USD
    """
    try:
        ticker_ba = f"{ticker}.BA"
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=periodo_dias + 30)
        
        # Usar yf.download en lugar de Ticker
        df = yf.download(ticker_ba, start=start_date, end=end_date, progress=False)
        
        if df.empty:
            return None, None
        
        # Si df_tc es None, usar TC fijo actual
        if df_tc is None:
            tc_actual, _, _ = obtener_tipo_cambio_actual()
            if tc_actual is None:
                return None, None
            
            df_combined = pd.DataFrame({
                'Close_ARS': df['Close'],
                'Volume': df['Volume'],
                'TC': tc_actual  # TC fijo
            })
        else:
            # Crear DataFrame combinado
            df_combined = pd.DataFrame({
                'Close_ARS': df['Close'],
                'Volume': df['Volume']
            })
            
            # Mergear con tipo de cambio
            df_combined = df_combined.join(df_tc[['TC']], how='left')
            
            # Forward/backward fill para días sin TC
            df_combined['TC'] = df_combined['TC'].ffill().bfill()
        
        # Calcular precio en USD
        df_combined['Close_USD'] = df_combined['Close_ARS'] / df_combined['TC']
        
        # Eliminar filas con NaN
        df_combined = df_combined.dropna()
        
        return df_combined, ticker_ba
        
    except Exception as e:
        st.warning(f"Error obteniendo datos de {ticker}: {e}")
        return None, None

# Función principal de análisis
def analizar_accion(ticker, df_tc, periodo_rsi=14):
    """
    Analiza una acción y retorna sus métricas
    """
    df, ticker_completo = obtener_datos_accion_usd(ticker, df_tc)
    
    if df is None or df.empty:
        return None
    
    # Calcular RSI en ARS
    df['RSI_ARS'] = calcular_rsi(df['Close_ARS'], periodo_rsi)
    
    # Calcular RSI en USD (¡ESTO ES LO IMPORTANTE!)
    df['RSI_USD'] = calcular_rsi(df['Close_USD'], periodo_rsi)
    
    # Valores actuales
    precio_ars = df['Close_ARS'].iloc[-1]
    precio_usd = df['Close_USD'].iloc[-1]
    tc_actual = df['TC'].iloc[-1]
    rsi_ars = df['RSI_ARS'].iloc[-1]
    rsi_usd = df['RSI_USD'].iloc[-1]
    
    return {
        'ticker': ticker,
        'ticker_completo': ticker_completo,
        'precio_ars': precio_ars,
        'precio_usd': precio_usd,
        'tc': tc_actual,
        'rsi_ars': rsi_ars,
        'rsi_usd': rsi_usd,
        'df': df
    }

# Sidebar con configuración
st.sidebar.header("⚙️ Configuración")

periodo_rsi = st.sidebar.slider(
    "Período RSI",
    min_value=7,
    max_value=30,
    value=14,
    help="Cantidad de períodos para calcular el RSI"
)

periodo_dias = st.sidebar.slider(
    "Días históricos",
    min_value=30,
    max_value=365,
    value=90,
    help="Cantidad de días de historia a analizar"
)

# Lista de tickers predefinidos
st.sidebar.header("📋 Acciones Predefinidas")
tickers_predefinidos = ["GGAL", "YPF", "BBAR", "BMA", "CEPU", "EDN", "LOMA", "PAM", "YPFD", "TXAR", "ALUA", "COME", "CRES"]

usar_predefinidos = st.sidebar.checkbox("Usar lista predefinida", value=True)

if usar_predefinidos:
    tickers_seleccionados = st.sidebar.multiselect(
        "Selecciona acciones:",
        tickers_predefinidos,
        default=["GGAL", "YPF", "BBAR"]
    )
else:
    st.sidebar.markdown("**Ingresar tickers manualmente:**")
    tickers_input = st.sidebar.text_area(
        "Un ticker por línea:",
        "HAVA\nBYMA\nMOLA",
        height=150
    )
    tickers_seleccionados = [t.strip().upper() for t in tickers_input.split('\n') if t.strip()]

# Sección principal
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.header("💵 Tipo de Cambio Implícito")
    
    if st.button("🔄 Actualizar Datos", type="secondary"):
        st.cache_data.clear()
    
    with st.spinner("Obteniendo tipo de cambio actual..."):
        tc_actual, precio_ba, precio_us = obtener_tipo_cambio_actual()
    
    if tc_actual:
        st.success(f"**TC Actual: ${tc_actual:.2f}**")
        st.caption(f"GGAL.BA: ${precio_ba:.2f} | GGAL (NASDAQ): USD ${precio_us:.2f}")
    else:
        st.error("No se pudo obtener el tipo de cambio")
        st.stop()

with col2:
    st.metric("📊 Período RSI", periodo_rsi)

with col3:
    st.metric("📅 Días Históricos", periodo_dias)

# Info box
st.info("🎯 **Importante**: El RSI se calcula sobre los precios históricos en USD, usando el tipo de cambio implícito de GGAL para cada día.")

st.divider()

# Sección de cálculo
st.header("🎯 Calcular RSI en USD")

if st.button("🚀 CALCULAR RSI DE TODAS LAS ACCIONES", type="primary", use_container_width=True):
    
    if not tickers_seleccionados:
        st.warning("⚠️ No hay acciones seleccionadas")
        st.stop()
    
    # Obtener tipo de cambio histórico primero
    with st.spinner("Obteniendo tipo de cambio histórico de GGAL..."):
        df_tc = obtener_tipo_cambio_historico(periodo_dias + 30)
    
    # Si no se pudo obtener TC histórico, ofrecer usar TC fijo
    if df_tc is None or df_tc.empty:
        st.warning("⚠️ No se pudo obtener TC histórico. ¿Usar tipo de cambio actual para todo el período?")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sí, usar TC fijo"):
                tc_actual, _, _ = obtener_tipo_cambio_actual()
                if tc_actual:
                    st.info(f"Usando TC fijo: ${tc_actual:.2f}")
                    # Continuar con TC fijo (se maneja en obtener_datos_accion_usd)
                    df_tc = None
                else:
                    st.error("❌ No se pudo obtener ni TC histórico ni actual.")
                    st.stop()
            else:
                st.stop()
        with col2:
            if st.button("No, cancelar"):
                st.stop()
    else:
        st.success(f"✅ TC histórico obtenido ({len(df_tc)} días)")
    
    # Crear contenedor para resultados
    resultados = []
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Procesar cada ticker
    for idx, ticker in enumerate(tickers_seleccionados):
        status_text.text(f"Procesando {ticker}... ({idx + 1}/{len(tickers_seleccionados)})")
        
        resultado = analizar_accion(ticker, df_tc, periodo_rsi)
        
        if resultado:
            resultados.append(resultado)
        
        progress_bar.progress((idx + 1) / len(tickers_seleccionados))
    
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
                'RSI (ARS)': f"{r['rsi_ars']:.2f}",
                'RSI (USD)': f"{r['rsi_usd']:.2f}",
                'Diferencia': f"{(r['rsi_usd'] - r['rsi_ars']):.2f}",
                'Señal': '🟢 Sobreventa' if r['rsi_usd'] < 30 else ('🔴 Sobrecompra' if r['rsi_usd'] > 70 else '🟡 Neutral')
            }
            for r in resultados
        ])
        
        # Mostrar tabla
        st.dataframe(
            df_resultados,
            use_container_width=True,
            hide_index=True
        )
        
        # Explicación de las columnas
        with st.expander("ℹ️ ¿Qué significa cada columna?"):
            st.markdown("""
            - **RSI (ARS)**: RSI calculado sobre precios en pesos argentinos
            - **RSI (USD)**: RSI calculado sobre precios en dólares (usando TC histórico) ← **Este es el correcto**
            - **Diferencia**: Diferencia entre RSI USD y ARS (muestra el efecto de la devaluación)
            """)
        
        # Descargar CSV
        csv = df_resultados.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar resultados (CSV)",
            data=csv,
            file_name=f"rsi_usd_acciones_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
        # Gráficos individuales
        st.divider()
        st.header("📊 Gráficos Detallados")
        
        ticker_graficar = st.selectbox(
            "Selecciona una acción para ver detalle:",
            [r['ticker'] for r in resultados]
        )
        
        resultado_sel = next(r for r in resultados if r['ticker'] == ticker_graficar)
        df_grafico = resultado_sel['df']
        
        # Crear subplots
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(
                f'{ticker_graficar} - Precio en USD', 
                'RSI en USD vs RSI en ARS',
                'Tipo de Cambio Implícito'
            ),
            row_heights=[0.4, 0.35, 0.25]
        )
        
        # Subplot 1: Precio en USD
        fig.add_trace(
            go.Scatter(
                x=df_grafico.index,
                y=df_grafico['Close_USD'],
                name='Precio USD',
                line=dict(color='blue', width=2)
            ),
            row=1, col=1
        )
        
        # Subplot 2: RSI USD y ARS
        fig.add_trace(
            go.Scatter(
                x=df_grafico.index,
                y=df_grafico['RSI_USD'],
                name='RSI (USD)',
                line=dict(color='green', width=2)
            ),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df_grafico.index,
                y=df_grafico['RSI_ARS'],
                name='RSI (ARS)',
                line=dict(color='orange', width=2, dash='dash')
            ),
            row=2, col=1
        )
        
        # Líneas de referencia RSI
        fig.add_hline(y=70, line_dash="dot", line_color="red", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", opacity=0.5, row=2, col=1)
        
        # Subplot 3: Tipo de Cambio
        fig.add_trace(
            go.Scatter(
                x=df_grafico.index,
                y=df_grafico['TC'],
                name='TC GGAL',
                line=dict(color='purple', width=2),
                fill='tozeroy'
            ),
            row=3, col=1
        )
        
        # Layout
        fig.update_xaxes(title_text="Fecha", row=3, col=1)
        fig.update_yaxes(title_text="USD", row=1, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
        fig.update_yaxes(title_text="ARS/USD", row=3, col=1)
        
        fig.update_layout(
            height=800,
            hovermode='x unified',
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Métricas adicionales
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Precio (ARS)", f"${resultado_sel['precio_ars']:.2f}")
        
        with col2:
            st.metric("Precio (USD)", f"${resultado_sel['precio_usd']:.2f}")
        
        with col3:
            st.metric("RSI (USD)", f"{resultado_sel['rsi_usd']:.2f}")
        
        with col4:
            st.metric("RSI (ARS)", f"{resultado_sel['rsi_ars']:.2f}")
        
        with col5:
            diff_rsi = resultado_sel['rsi_usd'] - resultado_sel['rsi_ars']
            st.metric("Diferencia RSI", f"{diff_rsi:.2f}")
        
        # Análisis adicional
        st.markdown("---")
        st.subheader("📈 Análisis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Interpretación RSI (USD):**")
            if resultado_sel['rsi_usd'] < 30:
                st.success("🟢 **SOBREVENTA** - Posible oportunidad de compra")
            elif resultado_sel['rsi_usd'] > 70:
                st.error("🔴 **SOBRECOMPRA** - Posible oportunidad de venta")
            else:
                st.info("🟡 **NEUTRAL** - Sin señales extremas")
        
        with col2:
            st.markdown("**Efecto de la devaluación:**")
            if abs(diff_rsi) < 5:
                st.info("Diferencia mínima entre RSI USD y ARS")
            elif diff_rsi > 5:
                st.warning("RSI en USD es más alto - La acción subió más que la devaluación")
            else:
                st.warning("RSI en USD es más bajo - La acción no siguió el ritmo de la devaluación")
    
    else:
        st.error("❌ No se pudieron procesar las acciones")

# Footer
st.divider()
st.caption("💡 **Nota**: El RSI en USD considera el tipo de cambio implícito histórico, dando una visión más precisa del momentum real sin el efecto de la devaluación.")
st.caption(f"🕒 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")