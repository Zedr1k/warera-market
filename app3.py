# app3.py
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime
import json

# Configuración de la página
st.set_page_config(page_title="WarEra Market Dashboard", layout="wide")

# URL de la API
API_URL = "https://api2.warera.io/trpc/tradingOrder.getTopOrders"
PRICES_URL = 'https://api2.warera.io/trpc/itemTrading.getPrices?batch=1&input={"0":{"limit":100}}'

# Datos de producción (recetas)
PRODUCTION_DATA = {
    "steak": {"ingredients": {"livestock": 1}, "pp": 20},
    "livestock": {"ingredients": {}, "pp": 20},
    "coca": {"ingredients": {}, "pp": 1},
    "cocain": {"ingredients": {"coca": 200}, "pp": 200},
    "cookedFish": {"ingredients": {"fish": 1}, "pp": 40},
    "heavyAmmo": {"ingredients": {"lead": 16}, "pp": 16},
    "concrete": {"ingredients": {"limestone": 10}, "pp": 10},
    "fish": {"ingredients": {}, "pp": 40},
    "bread": {"ingredients": {"grain": 10}, "pp": 10},
    "ammo": {"ingredients": {"lead": 4}, "pp": 4},
    "limestone": {"ingredients": {}, "pp": 1},
    "grain": {"ingredients": {}, "pp": 1},
    "iron": {"ingredients": {}, "pp": 1},
    "steel": {"ingredients": {"iron": 10}, "pp": 10},
    "lead": {"ingredients": {}, "pp": 1},
    "lightAmmo": {"ingredients": {"lead": 1}, "pp": 1},
    "oil": {"ingredients": {"petroleum": 1}, "pp": 1},
    "petroleum": {"ingredients": {}, "pp": 1}
}

# Función para obtener precios de mercado
@st.cache_data
def get_market_prices():
    """Obtiene precios actuales del mercado desde la API"""
    try:
        response = requests.get(PRICES_URL)
        data = response.json()
        return data[0]['result']['data']
    except:
        st.error("Error obteniendo precios de mercado")
        return {}

# Función para calcular costos de producción
def calculate_production_cost(resource, cost_per_pp, production_bonus, cache=None):
    """Calcula recursivamente el costo de producción de un recurso con bonus"""
    if cache is None:
        cache = {}
    
    if resource in cache:
        return cache[resource]
    
    recipe = PRODUCTION_DATA[resource]
    
    # Calcular PP efectivo considerando el bonus
    effective_pp = recipe["pp"] / (1 + production_bonus)
    total_cost = effective_pp * cost_per_pp
    
    for ingredient, quantity in recipe["ingredients"].items():
        ingredient_cost = calculate_production_cost(ingredient, cost_per_pp, production_bonus, cache)
        total_cost += quantity * ingredient_cost
    
    cache[resource] = total_cost
    return total_cost

# Función para calcular ROI
def calculate_roi(cost_per_pp, production_bonus):
    """Calcula el ROI para todos los recursos considerando el bonus de producción"""
    market_prices = get_market_prices()
    
    if not market_prices:
        st.error("No se pudieron obtener los precios de mercado")
        return []
    
    results = []
    cache = {}
    
    for resource, market_price in market_prices.items():
        if resource not in PRODUCTION_DATA:
            continue
            
        try:
            production_cost = calculate_production_cost(resource, cost_per_pp, production_bonus, cache)
            profit = market_price - production_cost
            roi = (profit / production_cost) * 100 if production_cost > 0 else float('inf')
            results.append({
                "resource": resource,
                "market_price": market_price,
                "production_cost": production_cost,
                "profit_per_unit": profit,
                "roi": roi
            })
        except KeyError:
            continue
    
    return results

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

# Barra lateral
st.sidebar.title("🔍 Market Explorer")
item_options = [
    "petroleum", "lead", "coca", "iron", "fish", "livestock", "grain", "limestone", "oil",
    "lightAmmo", "bread", "steel", "concrete", "ammo", "steak", "heavyAmmo", "cocain", "cookedFish", "case1"
]
item_code = st.sidebar.selectbox("Item Code", options=item_options, index=0)
limit = st.sidebar.slider("Order Limit", min_value=1, max_value=50, value=10)

# Sección de ROI en la barra lateral
st.sidebar.title("📊 ROI Calculator")
cost_per_pp = st.sidebar.number_input("Costo por PP", min_value=0.001, max_value=1.0, value=0.064, step=0.001)
production_bonus = st.sidebar.slider("Bonus de Producción (%)", min_value=0, max_value=100, value=27) / 100

# Cálculo de ROI
roi_data = calculate_roi(cost_per_pp, production_bonus)

# Pestañas para la visualización
tab1, tab2 = st.tabs(["📈 Market Depth", "📊 ROI Analysis"])

with tab1:
    st.title(f"📈 Market Depth Chart for {item_code}")
    
    # Carga de datos
    buy_orders, sell_orders = fetch_market_orders(item_code, limit)
    buy_df = pd.DataFrame(buy_orders)
    buy_df = buy_df[buy_df['price'] > 0.002]                    
    sell_df = pd.DataFrame(sell_orders)

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

with tab2:
    st.title("📊 ROI Analysis")
    
    if roi_data:
        # Crear DataFrame con los resultados
        roi_df = pd.DataFrame(roi_data)
        roi_df = roi_df.sort_values('roi', ascending=False)
        
        # Mostrar métricas principales
        best_roi = roi_df.iloc[0]
        worst_roi = roi_df.iloc[-1]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mejor ROI", f"{best_roi['roi']:.2f}%", best_roi['resource'])
        with col2:
            st.metric("Peor ROI", f"{worst_roi['roi']:.2f}%", worst_roi['resource'])
        with col3:
            profitable = len(roi_df[roi_df['roi'] > 0])
            st.metric("Recursos Rentables", f"{profitable}/{len(roi_df)}")
        
        # Mostrar tabla de ROI
        st.subheader("ROI por Recurso")
        st.dataframe(
            roi_df.style.format({
                'market_price': '{:.4f}',
                'production_cost': '{:.4f}',
                'profit_per_unit': '{:.4f}',
                'roi': '{:.2f}%'
            }),
            use_container_width=True
        )
        
        # Gráfico de barras de ROI
        fig_roi = go.Figure()
        fig_roi.add_trace(go.Bar(
            x=roi_df['resource'],
            y=roi_df['roi'],
            marker_color=['green' if roi > 0 else 'red' for roi in roi_df['roi']]
        ))
        fig_roi.update_layout(
            title='ROI por Recurso',
            xaxis_title='Recurso',
            yaxis_title='ROI (%)',
            xaxis_tickangle=-45,
            height=500
        )
        st.plotly_chart(fig_roi, use_container_width=True)
        
        # Mostrar detalles de los 5 mejores recursos
        st.subheader("Top 5 Recursos por ROI")
        top_5 = roi_df.head()
        for _, row in top_5.iterrows():
            with st.expander(f"{row['resource']} - ROI: {row['roi']:.2f}%"):
                st.write(f"**Precio de mercado:** ${row['market_price']:.4f}")
                st.write(f"**Costo de producción:** ${row['production_cost']:.4f}")
                st.write(f"**Beneficio por unidad:** ${row['profit_per_unit']:.4f}")
                st.write(f"**ROI:** {row['roi']:.2f}%")
    else:
        st.warning("No se pudo calcular el ROI. Verifique la conexión a internet.")
