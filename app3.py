# app3.py
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="WarEra Market Dashboard", layout="wide")

# URL de la API
API_URL = "https://api2.warera.io/trpc/tradingOrder.getTopOrders"

# Controles en la barra lateral
st.sidebar.title("🔍 Market Explorer")
item_options = [
    "petroleum", "lead", "coca", "iron", "fish", "livestock", "grain", "limestone", "oil",
    "lightAmmo", "bread", "steel", "concrete", "ammo", "steak", "heavyAmmo", "cocain", "cookedFish", "case1"
]
item_code = st.sidebar.selectbox("Item Code", options=item_options, index=0)
limit = st.sidebar.slider("Order Limit", min_value=1, max_value=50, value=10)

# Función para obtener órdenes de mercado
@st.cache_data
def fetch_market_orders(item_code, limit):
    params = {
        "batch": "1",
        "input": f"{{\"0\":{{\"itemCode\":\"{item_code}\", \"limit\":{limit}}}}}"
    }
    try:
        res = requests.get(API_URL, params=params)
        res.raise_for_status()
        data = res.json()[0]['result']['data']
        return data['buyOrders'], data['sellOrders']
    except Exception as e:
        st.error(f"❌ Error fetching market data: {e}")
        return [], []

# Carga de datos
buy_orders, sell_orders = fetch_market_orders(item_code, limit)
buy_df = pd.DataFrame(buy_orders)
sell_df = pd.DataFrame(sell_orders)

st.title(f"📈 Market Depth Chart for {item_code}")
                    
if not buy_df.empty or not sell_df.empty:
    # Métricas principales
    total_buy_cost = (sell_df['quantity'] * sell_df['price']).sum()
    total_buy_qty = sell_df['quantity'].sum()
    total_sell_revenue = (buy_df['quantity'] * buy_df['price']).sum()
    total_sell_qty = buy_df['quantity'].sum()
    highest_bid = buy_df['price'].max() if not buy_df.empty else None
    lowest_ask = sell_df['price'].min() if not sell_df.empty else None
    if highest_bid is not None and lowest_ask is not None:
        spread = lowest_ask - highest_bid
        per = ((lowest_ask - highest_bid) / lowest_ask) * 100
    else:
        spread, per = "-", "-"

    colA, colB, colC = st.columns(3)
    with colA:
        st.metric(label="Cost to Buy All Asks", value=f"$ {total_buy_cost:.2f}", delta=f"{int(total_buy_qty)} units")
    with colB:
        st.metric(label="Revenue Selling Into All Bids", value=f"$ {total_sell_revenue:.2f}", delta=f"-{int(total_sell_qty)} units")
    with colC:
        st.metric(label="Bid-Ask Spread", value=f"{per:.1f}%", delta=f"{spread:.2f}")

    # Preparar DataFrames para el depth chart
    # Sell: acumulación de izquierda a derecha (precios ascendentes)
    sell_df = sell_df.sort_values(by='price')
    sell_df['cum_qty'] = sell_df['quantity'].cumsum()
    sell_df['side'] = 'Sell'

    # Buy: acumulación de derecha a izquierda (precios descendentes)
    buy_df = buy_df.sort_values(by='price', ascending=False)
    buy_df['cum_qty'] = buy_df['quantity'].cumsum()
    buy_df['side'] = 'Buy'

    # Depth chart con Plotly
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=buy_df['price'],
        y=buy_df['cum_qty'],
        mode='lines',
        line_shape='hv',
        fill='tozeroy',
        name='Buy',
        line=dict(color='green')
    ))
    fig.add_trace(go.Scatter(
        x=sell_df['price'],
        y=sell_df['cum_qty'],
        mode='lines',
        line_shape='hv',
        fill='tozeroy',
        name='Sell',
        line=dict(color='red')
    ))
    fig.update_layout(
        title='Depth Chart',
        xaxis_title='Precio',
        yaxis_title='Cantidad Acumulada',
        width=800,
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tablas de órdenes
    st.subheader("Order Details")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Buy Orders**")
        st.dataframe(buy_df[['price', 'quantity']], use_container_width=True)
    with col2:
        st.markdown("**Sell Orders**")
        st.dataframe(sell_df[['price', 'quantity']], use_container_width=True)
else:
    st.warning("No buy or sell orders available for este item.")
