# app.py
import streamlit as st
import pandas as pd
import requests
import altair as alt
from datetime import datetime

st.set_page_config(page_title="WarEra Market Dashboard", layout="wide")

# API URL
API_URL = "https://api2.warera.io/trpc/tradingOrder.getTopOrders"

# Sidebar controls
st.sidebar.title("🔍 Market Explorer")
# Sidebar Item selection using combobox
t_ITEM_OPTIONS = ["petroleum", "lead", "coca", "iron", "fish", "livestock", "grain", "limestone", "oil", "lightAmmo", "bread"
                  , "steel", "concrete", "ammo", "steak", "heavyAmmo", "cocain", "cookedFish", "case1"]
item_code = st.sidebar.selectbox("Item Code", options=t_ITEM_OPTIONS, index=0)
limit = st.sidebar.slider("Order Limit", min_value=1, max_value=50, value=10)

# Fetch data function
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

# Fetch data
buy_orders, sell_orders = fetch_market_orders(item_code, limit)

# Convert to DataFrame
buy_df = pd.DataFrame(buy_orders)
buy_df = buy_df[buy_df['price'] > 0.001]
sell_df = pd.DataFrame(sell_orders)

st.title(f"📈 Market Depth Chart for `{item_code}`")

if not buy_df.empty or not sell_df.empty:
    # Metrics: cost to buy all asks and revenue selling into bids
    total_buy_cost = (sell_df['quantity'] * sell_df['price']).sum()
    total_buy_qty = sell_df['quantity'].sum()
    total_sell_revenue = (buy_df['quantity'] * buy_df['price']).sum()
    total_sell_qty = buy_df['quantity'].sum()
    highest_bid = buy_df['price'].max() if not buy_df.empty else None
    lowest_ask = sell_df['price'].min() if not sell_df.empty else None
    if highest_bid is not None and lowest_ask is not None:
        spread = lowest_ask - highest_bid
        per = ((lowest_ask - highest_bid) / lowest_ask)*100
    else:
        spread = "-"
        per = "-"
    colA, colB, colC = st.columns(3)
    with colA:
        st.metric(label="Cost to Buy All Asks", value=f"$ {total_buy_cost:.2f}", delta=f"{int(total_buy_qty)} units")
    with colB:
        st.metric(label="Revenue Selling Into All Bids", value=f"$ {total_sell_revenue:.2f}", delta=f"-{int(total_sell_qty)} units")
    with colC:
        st.metric(label="Bid-Ask Spread", value=f"{per:.1f}%", delta=f"{spread:.2f}")

if not buy_df.empty or not sell_df.empty:
    # Add side column
    buy_df['side'] = 'Buy'
    sell_df['side'] = 'Sell'

    # Sort and calculate cumulative quantities (all positive)
    buy_df_sorted = buy_df.sort_values(by='price', ascending=False)
    buy_df_sorted['cum_qty'] = buy_df_sorted['quantity'].cumsum()
    buy_df_sorted['plot_qty'] = buy_df_sorted['cum_qty']  # positive for buy

    sell_df_sorted = sell_df.sort_values(by='price')
    sell_df_sorted['cum_qty'] = sell_df_sorted['quantity'].cumsum()
    sell_df_sorted['plot_qty'] = sell_df_sorted['cum_qty']  # positive for sell

    chart_df = pd.concat([
        buy_df_sorted[['price', 'plot_qty', 'side']],
        sell_df_sorted[['price', 'plot_qty', 'side']]
    ])

    # Depth chart: buy in green, sell in red
    depth_chart = alt.Chart(chart_df).mark_area(opacity=0.6).encode(
        x=alt.X('price:Q', title='Price'),
        y=alt.Y('plot_qty:Q', title='Cumulative Quantity'),
        color=alt.Color('side:N', scale=alt.Scale(domain=['Buy','Sell'], range=['green','red'])),
        tooltip=['side', 'price', 'plot_qty']
    ).properties(
        width=800,
        height=400
    )

    st.altair_chart(depth_chart, use_container_width=True)
    


    # Show order tables side by side
    st.subheader("Order Details")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Buy Orders**")
        st.dataframe(buy_df[['price','quantity']], use_container_width=True)
    with col2:
        st.markdown("**Sell Orders**")
        st.dataframe(sell_df[['price','quantity']], use_container_width=True)
else:
    st.warning("No buy or sell orders available for this item.")
