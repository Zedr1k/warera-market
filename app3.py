import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import urllib.parse

# Configuración de la página
st.set_page_config(page_title="WarEra Market Dashboard", layout="wide")

# URLs de la API
API_URL = "https://api2.warera.io/trpc/tradingOrder.getTopOrders"
PRICES_URL = "https://api2.warera.io/trpc/itemTrading.getPrices?batch=1&input=%7B%220%22%3A%7B%22limit%22%3A100%7D%7D"

# URLs para empresas
def get_companies_url(user_id):
    """Genera la URL para obtener empresas de un usuario"""
    input_json = json.dumps({"0": {"userId": user_id}})
    encoded_input = urllib.parse.quote(input_json)
    return f"https://api2.warera.io/trpc/company.getCompanies?batch=1&input={encoded_input}"

def get_company_details_url(company_id):
    """Genera la URL para obtener detalles de una empresa"""
    input_json = json.dumps({"0": {"companyId": company_id}})
    encoded_input = urllib.parse.quote(input_json)
    return f"https://api2.warera.io/trpc/company.getById?batch=1&input={encoded_input}"

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

# Lista de materias primas (recursos sin ingredientes)
RAW_MATERIALS = [resource for resource, data in PRODUCTION_DATA.items() if not data.get('ingredients')]

# Función para obtener precios de mercado
@st.cache_data
def get_market_prices():
    """Obtiene precios actuales del mercado desde la API"""
    try:
        response = requests.get(PRICES_URL)
        data = response.json()
        return data[0]['result']['data']
    except Exception as e:
        st.error(f"Error obteniendo precios de mercado: {str(e)}")
        return {}

# Función para obtener empresas de un usuario
@st.cache_data
def get_user_companies(user_id):
    """Obtiene las empresas de un usuario"""
    try:
        url = get_companies_url(user_id)
        response = requests.get(url)
        
        if response.status_code != 200:
            st.error(f"Error en la respuesta HTTP: {response.status_code}")
            return []
            
        data = response.json()
        return data[0]['result']['data']['items']
    except Exception as e:
        st.error(f"Error obteniendo empresas del usuario: {str(e)}")
        return []

# Función para obtener detalles de una empresa
@st.cache_data
def get_company_details(company_id):
    """Obtiene los detalles de una empresa específica"""
    try:
        url = get_company_details_url(company_id)
        response = requests.get(url)
        
        if response.status_code != 200:
            st.error(f"Error en la respuesta HTTP: {response.status_code}")
            return None
            
        data = response.json()
        return data[0]['result']['data']
    except Exception as e:
        st.error(f"Error obteniendo detalles de la empresa {company_id}: {str(e)}")
        return None

# Función para calcular costos de producción usando precios de mercado para materias primas
def calculate_production_cost_with_market(resource, cost_per_pp, production_bonus, market_prices, cache=None):
    """Calcula recursivamente el costo de producción de un recurso con bonus y precios de mercado para materias primas"""
    if cache is None:
        cache = {}
    
    if resource in cache:
        return cache[resource]
    
    recipe = PRODUCTION_DATA[resource]
    
    # Calcular PP efectivo considerando el bonus
    effective_pp = recipe["pp"] / (1 + production_bonus)
    total_cost = effective_pp * cost_per_pp
    
    for ingredient, quantity in recipe["ingredients"].items():
        # Usar precio de mercado para materias primas
        if ingredient in market_prices:
            ingredient_cost = market_prices[ingredient]
        else:
            # Si no hay precio de mercado, calcular recursivamente
            ingredient_cost = calculate_production_cost_with_market(ingredient, cost_per_pp, production_bonus, market_prices, cache)
        
        total_cost += quantity * ingredient_cost
    
    cache[resource] = total_cost
    return total_cost

# Función para calcular el máximo costo por PP que mantiene ganancias
def calculate_max_pp_cost(resource, production_bonus, market_prices, use_deposit_bonus=False):
    """Calcula el máximo costo por PP que mantiene ganancias para un recurso"""
    if resource not in PRODUCTION_DATA or resource not in market_prices:
        return None
    
    market_price = market_prices[resource]
    recipe = PRODUCTION_DATA[resource]
    
    # Ajustar bonus para materias primas si se usa el bonus de depósito
    effective_bonus = production_bonus
    if use_deposit_bonus and resource in RAW_MATERIALS:
        effective_bonus += 0.3
    
    # Calcular PP efectivo considerando el bonus
    effective_pp = recipe["pp"] / (1 + effective_bonus)
    
    # Calcular el costo de los ingredientes usando precios de mercado
    ingredient_cost = 0
    for ingredient, quantity in recipe.get("ingredients", {}).items():
        if ingredient in market_prices:
            ingredient_cost += quantity * market_prices[ingredient]
        else:
            # Si no hay precio de mercado, no podemos calcular
            return None
    
    # Calcular el máximo costo por PP que mantiene ganancias
    # production_cost = effective_pp * cost_per_pp + ingredient_cost <= market_price
    # => cost_per_pp <= (market_price - ingredient_cost) / effective_pp
    if market_price <= ingredient_cost:
        return 0  # No es rentable incluso con PP gratis
    
    max_cost_per_pp = (market_price - ingredient_cost) / effective_pp
    return max_cost_per_pp

# Función para analizar empleados con costos reales
def analyze_employees_with_real_costs(user_id, production_bonus):
    """Analiza la rentabilidad de cada empleado individualmente usando su salario como costo por PP"""
    companies = get_user_companies(user_id)
    market_prices = get_market_prices()
    
    if not companies or not market_prices:
        return []
    
    employees_analysis = []
    
    for company_id in companies:
        company = get_company_details(company_id)
        if not company:
            continue
            
        resource = company.get('itemCode')
        if resource not in PRODUCTION_DATA:
            continue
        
        # Obtener precio de mercado del recurso
        market_price = market_prices.get(resource, 0)
        
        # Analizar cada empleado
        workers = company.get('workers', [])
        for worker in workers:
            wage = worker.get('wage', 0)
            worker_id = worker.get('user', '')
            
            # Calcular costo de producción usando el salario del empleado como costo por PP
            production_cost = calculate_production_cost_with_market(resource, wage, production_bonus, market_prices)
            
            # Calcular ganancia por unidad
            profit_per_unit = market_price - production_cost
            
            # Calcular porcentaje de ganancia
            profit_percentage = (profit_per_unit / production_cost) * 100 if production_cost > 0 else float('inf')
            
            # Determinar si es rentable
            is_profitable = profit_per_unit > 0
            
            employees_analysis.append({
                "company_name": company.get('name', 'Unknown'),
                "resource": resource,
                "worker_id": worker_id,
                "wage": wage,
                "production_cost": production_cost,
                "market_price": market_price,
                "profit_per_unit": profit_per_unit,
                "profit_percentage": profit_percentage,
                "is_profitable": is_profitable
            })
    
    return employees_analysis

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

# Nueva función: obtener trades (historial) usando transaction.getPaginatedTransactions
def fetch_trades(item_code, max_pages=20, headers=None):
    url = "https://api2.warera.io/trpc/transaction.getPaginatedTransactions"
    all_items = []
    cursor = None

    for _ in range(max_pages):
        payload = {"itemCode": item_code, "limit": 100}
        if cursor:
            payload["cursor"] = cursor
        params = {"batch": "1", "input": json.dumps({"0": payload})}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()[0].get("result", {}).get("data", {})
            items = data.get("items", [])
            if not items:
                break
            all_items.extend(items)
            cursor = data.get("nextCursor")
            if not cursor:
                break
        except Exception as e:
            st.warning(f"Error obteniendo transacciones para {item_code}: {e}")
            break

    return all_items


def fetch_24h_volume(item_code):
    url = "https://api2.warera.io/trpc/transaction.getPaginatedTransactions"
    cutoff = datetime.utcnow() - timedelta(hours=24)
    volume = 0.0
    cursor = None

    for _ in range(20):
        payload = {
            "itemCode": item_code,
            "limit": 100
        }
        if cursor:
            payload["cursor"] = cursor

        params = {
            "batch": "1",
            "input": json.dumps({"0": payload})
        }

        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()

        data = r.json()[0]["result"]["data"]
        items = data.get("items", [])

        if not items:
            break

        for t in items:
            ts = t.get("createdAt")
            if not ts:
                continue

            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
            if dt < cutoff:
                return volume

            volume += float(t.get("quantity", 0))

        cursor = data.get("nextCursor")
        if not cursor:
            break

    return volume

# Función para calcular máximos costos por PP para todos los recursos
def calculate_max_pp_costs(production_bonus):
    """Calcula el máximo costo por PP para todos los recursos"""
    market_prices = get_market_prices()
    
    if not market_prices:
        return []
    
    results = []
    
    for resource in PRODUCTION_DATA:
        if resource not in market_prices:
            continue
            
        market_price = market_prices[resource]
        
        # Calcular máximo costo por PP sin bonus de depósito
        max_cost_no_deposit = calculate_max_pp_cost(resource, production_bonus, market_prices, False)
        
        # Calcular máximo costo por PP con bonus de depósito (solo para materias primas)
        max_cost_with_deposit = None
        if resource in RAW_MATERIALS:
            max_cost_with_deposit = calculate_max_pp_cost(resource, production_bonus, market_prices, True)
        
        results.append({
            "resource": resource,
            "market_price": market_price,
            "max_cost_no_deposit": max_cost_no_deposit,
            "max_cost_with_deposit": max_cost_with_deposit,
            "is_raw_material": resource in RAW_MATERIALS
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

# Sección de análisis de empleados
st.sidebar.title("👥 Employee Analysis")
user_id = st.sidebar.text_input(
    "User ID", 
    value="68196d35dc610e77402347fa",
    help="Ingrese el ID del usuario para analizar sus empleados"
)

# Usamos un slider para el bonus pero con formato personalizado
production_bonus_percent = st.sidebar.slider(
    "Bonus de Producción (%)", 
    min_value=10, 
    max_value=35, 
    value=28,
    help="Porcentaje de bonus de producción (10-35%)"
)
production_bonus = production_bonus_percent / 100

# Análisis de empleados
analyze_employees_flag = st.sidebar.button("Analizar Empleados")

# Análisis de máximos costos por PP
analyze_max_costs_flag = st.sidebar.button("Calcular Máximos Costos PP")

# Nuevo: análisis de arbitrage (volumen + precio)
analyze_arbitrage_flag = st.sidebar.button("Analizar Arbitrage (24h)")

# Pestañas para la visualización (ahora con la nueva pestaña)
tab1, tab2, tab3, tab4 = st.tabs(["📈 Market Depth", "👥 Employee Analysis", "💰 Max PP Cost Analysis", "📊 Arbitrage Candidates"])

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
            name='Buy'
        ))
        fig.add_trace(go.Scatter(
            x=sell_df['price'],
            y=sell_df['cum_qty'],
            mode='lines',
            line_shape='hv',
            fill='tozeroy',
            name='Sell'
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
    st.title("👥 Employee Profitability Analysis")
    
    if analyze_employees_flag:
        with st.spinner("Analizando empleados..."):
            employees_data = analyze_employees_with_real_costs(user_id, production_bonus)
        
        if employees_data:
            # Crear DataFrame con los resultados
            employees_df = pd.DataFrame(employees_data)
            
            # Ordenar por porcentaje de ganancia (descendente)
            employees_df = employees_df.sort_values('profit_percentage', ascending=False)
            
            # Mostrar métricas generales
            profitable_employees = len(employees_df[employees_df['is_profitable']])
            total_employees = len(employees_df)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Empleados Rentables", f"{profitable_employees}/{total_employees}")
            with col2:
                avg_profit_percentage = employees_df['profit_percentage'].mean()
                st.metric("Ganancia Promedio", f"{avg_profit_percentage:.2f}%")
            with col3:
                total_profit = employees_df['profit_per_unit'].sum()
                st.metric("Ganancia Total", f"${total_profit:.2f}")
            
            # Mostrar tabla de empleados
            st.subheader("Análisis de Rentabilidad por Empleado")
            
            # Formatear la tabla para mejor visualización
            display_employees_df = employees_df.copy()
            display_employees_df['wage'] = display_employees_df['wage'].apply(lambda x: f"{x:.6f}")
            display_employees_df['production_cost'] = display_employees_df['production_cost'].apply(lambda x: f"{x:.6f}")
            display_employees_df['market_price'] = display_employees_df['market_price'].apply(lambda x: f"{x:.4f}")
            display_employees_df['profit_per_unit'] = display_employees_df['profit_per_unit'].apply(lambda x: f"{x:.6f}")
            display_employees_df['profit_percentage'] = display_employees_df['profit_percentage'].apply(lambda x: f"{x:.2f}%")
            
            # Reordenar columnas
            display_employees_df = display_employees_df[[
                'company_name', 'resource', 'worker_id', 'wage', 'production_cost',
                'market_price', 'profit_per_unit', 'profit_percentage', 'is_profitable'
            ]]
            
            st.dataframe(
                display_employees_df,
                use_container_width=True
            )
            
            # Gráfico de rentabilidad por empleado
            fig_employees = go.Figure()
            fig_employees.add_trace(go.Bar(
                x=employees_df['worker_id'],
                y=employees_df['profit_percentage'],
                text=employees_df['company_name'],
                textposition='auto'
            ))
            fig_employees.update_layout(
                title='Rentabilidad por Empleado (%)',
                xaxis_title='Empleado ID',
                yaxis_title='Porcentaje de Ganancia (%)',
                xaxis_tickangle=-45,
                height=500
            )
            st.plotly_chart(fig_employees, use_container_width=True)
            
            # Mostrar detalles de los mejores y peores empleados
            st.subheader("Top 5 Empleados Más Rentables")
            top_5 = employees_df.head()
            for _, employee in top_5.iterrows():
                with st.expander(f"Empleado {employee['worker_id']} - {employee['profit_percentage']:.2f}%"):
                    st.write(f"**Empresa:** {employee['company_name']}")
                    st.write(f"**Recurso:** {employee['resource']}")
                    st.write(f"**Salario:** ${employee['wage']:.6f} por PP")
                    st.write(f"**Costo de producción:** ${employee['production_cost']:.6f}")
                    st.write(f"**Precio de mercado:** ${employee['market_price']:.4f}")
                    st.write(f"**Ganancia por unidad:** ${employee['profit_per_unit']:.6f}")
                    st.write(f"**Porcentaje de ganancia:** {employee['profit_percentage']:.2f}%")
            
            st.subheader("Top 5 Empleados Menos Rentables")
            bottom_5 = employees_df.tail()
            for _, employee in bottom_5.iterrows():
                with st.expander(f"Empleado {employee['worker_id']} - {employee['profit_percentage']:.2f}%"):
                    st.write(f"**Empresa:** {employee['company_name']}")
                    st.write(f"**Recurso:** {employee['resource']}")
                    st.write(f"**Salario:** ${employee['wage']:.6f} por PP")
                    st.write(f"**Costo de producción:** ${employee['production_cost']:.6f}")
                    st.write(f"**Precio de mercado:** ${employee['market_price']:.4f}")
                    st.write(f"**Ganancia por unidad:** ${employee['profit_per_unit']:.6f}")
                    st.write(f"**Porcentaje de ganancia:** {employee['profit_percentage']:.2f}%")
        else:
            st.warning("No se pudieron analizar los empleados. Verifique el User ID y la conexión a internet.")
    else:
        st.info("Ingrese un User ID y haga clic en 'Analizar Empleados' para comenzar el análisis.")

with tab3:
    st.title("💰 Maximum PP Cost Analysis")
    
    if analyze_max_costs_flag:
        with st.spinner("Calculando máximos costos por PP..."):
            max_costs_data = calculate_max_pp_costs(production_bonus)
        
        if max_costs_data:
            # Crear DataFrame con los resultados
            max_costs_df = pd.DataFrame(max_costs_data)
            
            # Ordenar por máximo costo por PP (descendente)
            max_costs_df = max_costs_df.sort_values('max_cost_no_deposit', ascending=False)
            
            # Mostrar métricas generales
            profitable_resources = len(max_costs_df[max_costs_df['max_cost_no_deposit'] > 0])
            total_resources = len(max_costs_df)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Recursos Rentables", f"{profitable_resources}/{total_resources}")
            with col2:
                avg_max_cost = max_costs_df['max_cost_no_deposit'].mean()
                st.metric("Costo PP Promedio", f"${avg_max_cost:.6f}")
            with col3:
                raw_materials_count = len(max_costs_df[max_costs_df['is_raw_material']])
                st.metric("Materias Primas", f"{raw_materials_count}/{total_resources}")
            
            # Mostrar tabla de máximos costos
            st.subheader("Máximo Costo por PP para Mantener Ganancia")
            
            # Formatear la tabla para mejor visualización
            display_max_costs_df = max_costs_df.copy()
            display_max_costs_df['market_price'] = display_max_costs_df['market_price'].apply(lambda x: f"{x:.4f}")
            display_max_costs_df['max_cost_no_deposit'] = display_max_costs_df['max_cost_no_deposit'].apply(lambda x: f"{x:.6f}" if x is not None else "N/A")
            display_max_costs_df['max_cost_with_deposit'] = display_max_costs_df['max_cost_with_deposit'].apply(lambda x: f"{x:.6f}" if x is not None else "N/A")
            
            # Reordenar columnas
            display_max_costs_df = display_max_costs_df[[
                'resource', 'is_raw_material', 'market_price', 
                'max_cost_no_deposit', 'max_cost_with_deposit'
            ]]
            
            st.dataframe(
                display_max_costs_df,
                use_container_width=True
            )
            
            # Gráfico de máximos costos por PP
            fig_max_costs = go.Figure()
            fig_max_costs.add_trace(go.Bar(
                x=max_costs_df['resource'],
                y=max_costs_df['max_cost_no_deposit'],
                name='Sin Bonus Depósito'
            ))
            
            # Agregar barras para materias primas con bonus de depósito
            raw_materials_df = max_costs_df[max_costs_df['is_raw_material'] & max_costs_df['max_cost_with_deposit'].notnull()]
            if not raw_materials_df.empty:
                fig_max_costs.add_trace(go.Bar(
                    x=raw_materials_df['resource'],
                    y=raw_materials_df['max_cost_with_deposit'],
                    name='Con Bonus Depósito (30%)'
                ))
            
            fig_max_costs.update_layout(
                title='Máximo Costo por PP por Recurso',
                xaxis_title='Recurso',
                yaxis_title='Máximo Costo por PP',
                xaxis_tickangle=-45,
                height=500,
                barmode='group'
            )
            st.plotly_chart(fig_max_costs, use_container_width=True)
            
            # Mostrar detalles de los recursos más rentables
            st.subheader("Top 5 Recursos Más Rentables")
            top_5 = max_costs_df.head()
            for _, resource in top_5.iterrows():
                with st.expander(f"{resource['resource']} - Máximo PP: ${resource['max_cost_no_deposit']:.6f}"):
                    st.write(f"**Precio de mercado:** ${resource['market_price']:.4f}")
                    st.write(f"**Máximo costo por PP:** ${resource['max_cost_no_deposit']:.6f}")
                    if resource['is_raw_material'] and resource['max_cost_with_deposit'] is not None:
                        st.write(f"**Máximo costo con depósito (30%):** ${resource['max_cost_with_deposit']:.6f}")
                    st.write(f"**Es materia prima:** {'Sí' if resource['is_raw_material'] else 'No'}")
        else:
            st.warning("No se pudieron calcular los máximos costos. Verifique la conexión a internet.")
    else:
        st.info("Haga clic en 'Calcular Máximos Costos PP' para analizar los costos máximos por PP.")

with tab4:
    st.title("📊 Arbitrage Candidates — Precio Actual y Volumen 24h")
    st.write("En una sola tabla: todos los recursos, precio promedio actual (usado en Max PP Cost Analysis) y volumen de transacciones en las últimas 24 horas.")

    def calculate_bid_ask_spread(item_code, order_limit=100):
        try:
            buy_orders, sell_orders = fetch_market_orders(item_code, order_limit)
            buy_df = pd.DataFrame(buy_orders)
            sell_df = pd.DataFrame(sell_orders)
            if buy_df.empty or sell_df.empty:
                return None
            highest_bid = buy_df['price'].max()
            lowest_ask = sell_df['price'].min()
            return lowest_ask - highest_bid
        except Exception:
            return None

    if analyze_arbitrage_flag:
        with st.spinner("Calculando precios y volúmenes (esto puede tardar según la API)..."):
            market_prices = get_market_prices()
            rows = []
            for resource in sorted(PRODUCTION_DATA.keys()):
                price = market_prices.get(resource)
                volume_24h = fetch_24h_volume(resource)
                spread = calculate_bid_ask_spread(resource)
                rows.append({
                    'resource': resource,
                    'avg_price': price if price is not None else float('nan'),
                    'volume_24h': volume_24h,
                    'bid_ask_spread': spread
                })
            arb_df = pd.DataFrame(rows)
            arb_df_display = arb_df.sort_values(['volume_24h', 'avg_price'], ascending=[False, True])
            arb_df_display['avg_price'] = arb_df_display['avg_price'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "N/A")
            arb_df_display['volume_24h'] = arb_df_display['volume_24h'].apply(lambda x: f"{int(x)}" if pd.notna(x) and x is not None else "N/A")
            arb_df_display['bid_ask_spread'] = arb_df_display['bid_ask_spread'].apply(lambda x: f"{x:.6f}" if pd.notna(x) and x is not None else "N/A")
            st.dataframe(arb_df_display, use_container_width=True)

            st.markdown("**Notas:**")
            st.markdown("- `avg_price` viene de la misma llamada a precios usada en el análisis Max PP Cost.")
            st.markdown("- `volume_24h` se calcula sumando trades del historial (si la API lo provee). Si la API no devuelve historial, aparecerá `N/A`.")
            st.markdown("- `bid_ask_spread` se obtiene a partir de las órdenes activas (bid/ask) y coincide con lo mostrado en Market Depth.")
    else:
        st.info("Haga clic en 'Analizar Arbitrage (24h)' en la barra lateral para cargar la tabla de recursos con volumen y precio.")


