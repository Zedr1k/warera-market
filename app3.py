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
COMPANIES_URL = 'https://api2.warera.io/trpc/company.getCompanies?batch=1&input={"0":{"userId":"{user_id}"}}'
COMPANY_DETAILS_URL = 'https://api2.warera.io/trpc/company.getById?batch=1&input={"0":{"companyId":"{company_id}"}}'

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

# Función para obtener empresas de un usuario
@st.cache_data
def get_user_companies(user_id):
    """Obtiene las empresas de un usuario"""
    try:
        url = COMPANIES_URL.format(user_id=user_id)
        response = requests.get(url)
        data = response.json()
        return data[0]['result']['data']['items']
    except:
        st.error("Error obteniendo empresas del usuario")
        return []

# Función para obtener detalles de una empresa
@st.cache_data
def get_company_details(company_id):
    """Obtiene los detalles de una empresa específica"""
    try:
        url = COMPANY_DETAILS_URL.format(company_id=company_id)
        response = requests.get(url)
        data = response.json()
        return data[0]['result']['data']
    except:
        st.error(f"Error obteniendo detalles de la empresa {company_id}")
        return None

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

# Función para analizar empresas del usuario
def analyze_companies(user_id, cost_per_pp, production_bonus):
    """Analiza las empresas de un usuario para determinar rentabilidad"""
    companies = get_user_companies(user_id)
    market_prices = get_market_prices()
    
    if not companies or not market_prices:
        return []
    
    results = []
    
    for company_id in companies:
        company = get_company_details(company_id)
        if not company:
            continue
            
        resource = company.get('itemCode')
        if resource not in PRODUCTION_DATA:
            continue
            
        # Calcular costo de producción
        production_cost = calculate_production_cost(resource, cost_per_pp, production_bonus)
        market_price = market_prices.get(resource, 0)
        profit_per_unit = market_price - production_cost
        
        # Analizar trabajadores
        workers = company.get('workers', [])
        total_wage = sum(worker.get('wage', 0) for worker in workers)
        avg_wage = total_wage / len(workers) if workers else 0
        wage_status = "Below" if avg_wage < cost_per_pp else "Above"
        
        # Calcular rentabilidad
        is_profitable = profit_per_unit > 0
        profit_margin = (profit_per_unit / market_price) * 100 if market_price > 0 else 0
        
        results.append({
            "company_id": company_id,
            "name": company.get('name', 'Unknown'),
            "resource": resource,
            "production": company.get('production', 0),
            "worker_count": len(workers),
            "avg_wage": avg_wage,
            "cost_per_pp": cost_per_pp,
            "wage_status": wage_status,
            "production_cost": production_cost,
            "market_price": market_price,
            "profit_per_unit": profit_per_unit,
            "profit_margin": profit_margin,
            "is_profitable": is_profitable
        })
    
    return results

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

# Solución para el problema de precisión con number_input
cost_per_pp_default = 0.064
cost_per_pp_str = st.sidebar.text_input(
    "Costo por PP (ej: 0.064)", 
    value=str(cost_per_pp_default),
    help="Ingrese el costo por punto de producción con hasta 6 decimales"
)

try:
    cost_per_pp = float(cost_per_pp_str)
    if cost_per_pp <= 0 or cost_per_pp > 1:
        st.sidebar.error("El costo por PP debe ser mayor que 0 y menor o igual a 1")
        cost_per_pp = cost_per_pp_default
except ValueError:
    st.sidebar.error("Por favor ingrese un número válido")
    cost_per_pp = cost_per_pp_default

# Usamos un slider para el bonus pero con formato personalizado
production_bonus_percent = st.sidebar.slider(
    "Bonus de Producción (%)", 
    min_value=0, 
    max_value=200, 
    value=27,
    help="Porcentaje de bonus de producción (0-200%)"
)
production_bonus = production_bonus_percent / 100

# Sección para análisis de empresas
st.sidebar.title("🏢 Company Analysis")
user_id = st.sidebar.text_input(
    "User ID", 
    value="68196d35dc610e77402347fa",
    help="Ingrese el ID del usuario para analizar sus empresas"
)

# Cálculo de ROI
roi_data = calculate_roi(cost_per_pp, production_bonus)

# Análisis de empresas (solo si se solicita)
analyze_companies_flag = st.sidebar.button("Analizar Empresas")

# Pestañas para la visualización
tab1, tab2, tab3 = st.tabs(["📈 Market Depth", "📊 ROI Analysis", "🏢 Company Analysis"])

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
    
    # Mostrar los valores actuales de configuración
    st.sidebar.info(f"Configuración actual: Costo PP = {cost_per_pp:.6f}, Bonus = {production_bonus_percent}%")
    
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
        
        # Formatear la tabla para mejor visualización
        display_df = roi_df.copy()
        display_df['market_price'] = display_df['market_price'].apply(lambda x: f"{x:.4f}")
        display_df['production_cost'] = display_df['production_cost'].apply(lambda x: f"{x:.6f}")
        display_df['profit_per_unit'] = display_df['profit_per_unit'].apply(lambda x: f"{x:.6f}")
        display_df['roi'] = display_df['roi'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(
            display_df,
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
                st.write(f"**Costo de producción:** ${row['production_cost']:.6f}")
                st.write(f"**Beneficio por unidad:** ${row['profit_per_unit']:.6f}")
                st.write(f"**ROI:** {row['roi']:.2f}%")
    else:
        st.warning("No se pudo calcular el ROI. Verifique la conexión a internet.")

with tab3:
    st.title("🏢 Company Analysis")
    
    if analyze_companies_flag:
        with st.spinner("Analizando empresas..."):
            companies_data = analyze_companies(user_id, cost_per_pp, production_bonus)
        
        if companies_data:
            # Crear DataFrame con los resultados
            companies_df = pd.DataFrame(companies_data)
            
            # Mostrar métricas generales
            profitable_companies = len(companies_df[companies_df['is_profitable']])
            below_cost_companies = len(companies_df[companies_df['wage_status'] == 'Below'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Empresas Rentables", f"{profitable_companies}/{len(companies_df)}")
            with col2:
                st.metric("Salarios por Debajo", f"{below_cost_companies}/{len(companies_df)}")
            with col3:
                avg_margin = companies_df['profit_margin'].mean()
                st.metric("Margen Promedio", f"{avg_margin:.2f}%")
            
            # Mostrar tabla de empresas
            st.subheader("Análisis de Empresas")
            
            # Formatear la tabla para mejor visualización
            display_companies_df = companies_df.copy()
            display_companies_df['avg_wage'] = display_companies_df['avg_wage'].apply(lambda x: f"{x:.6f}")
            display_companies_df['production_cost'] = display_companies_df['production_cost'].apply(lambda x: f"{x:.6f}")
            display_companies_df['market_price'] = display_companies_df['market_price'].apply(lambda x: f"{x:.4f}")
            display_companies_df['profit_per_unit'] = display_companies_df['profit_per_unit'].apply(lambda x: f"{x:.6f}")
            display_companies_df['profit_margin'] = display_companies_df['profit_margin'].apply(lambda x: f"{x:.2f}%")
            
            # Reordenar columnas
            display_companies_df = display_companies_df[[
                'name', 'resource', 'worker_count', 'avg_wage', 'wage_status',
                'production_cost', 'market_price', 'profit_per_unit', 'profit_margin', 'is_profitable'
            ]]
            
            st.dataframe(
                display_companies_df,
                use_container_width=True
            )
            
            # Gráfico de rentabilidad
            fig_companies = go.Figure()
            fig_companies.add_trace(go.Bar(
                x=companies_df['name'],
                y=companies_df['profit_margin'],
                marker_color=['green' if profitable else 'red' for profitable in companies_df['is_profitable']],
                text=companies_df['resource'],
                textposition='auto'
            ))
            fig_companies.update_layout(
                title='Margen de Beneficio por Empresa',
                xaxis_title='Empresa',
                yaxis_title='Margen de Beneficio (%)',
                xaxis_tickangle=-45,
                height=500
            )
            st.plotly_chart(fig_companies, use_container_width=True)
            
            # Mostrar detalles de empresas problemáticas
            st.subheader("Empresas con Posibles Problemas")
            
            # Empresas no rentables
            unprofitable = companies_df[~companies_df['is_profitable']]
            if not unprofitable.empty:
                st.warning(f"{len(unprofitable)} empresas no son rentables")
                for _, company in unprofitable.iterrows():
                    with st.expander(f"{company['name']} - {company['resource']}"):
                        st.write(f"**Costo de producción:** ${company['production_cost']:.6f}")
                        st.write(f"**Precio de mercado:** ${company['market_price']:.4f}")
                        st.write(f"**Pérdida por unidad:** ${-company['profit_per_unit']:.6f}")
            
            # Empresas con salarios por encima del costo
            high_wage = companies_df[companies_df['wage_status'] == 'Above']
            if not high_wage.empty:
                st.info(f"{len(high_wage)} empresas con salarios por encima del costo de referencia")
                for _, company in high_wage.iterrows():
                    with st.expander(f"{company['name']} - Salario: {company['avg_wage']:.6f}"):
                        st.write(f"**Salario promedio:** ${company['avg_wage']:.6f}")
                        st.write(f"**Costo de referencia:** ${company['cost_per_pp']:.6f}")
                        st.write(f"**Diferencia:** ${company['avg_wage'] - company['cost_per_pp']:.6f}")
        else:
            st.warning("No se pudieron analizar las empresas. Verifique el User ID y la conexión a internet.")
    else:
        st.info("Ingrese un User ID y haga clic en 'Analizar Empresas' para comenzar el análisis.")
