# -*- coding: utf-8 -*-
"""
Created on Fri Feb  7 16:11:18 2025

@author: User
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import time
import streamlit as st
import threading

# Suppress warnings for cleaner output
import warnings
warnings.filterwarnings("ignore")

# Initialize the session state for keeping track of trades
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

# Step 1: Connect to MetaTrader 5
def connect_mt5(account_id, password, server):
    if not mt5.initialize():
        st.write("MT5 initialization failed.")
        mt5.shutdown()
        return False
    authorized = mt5.login(login=account_id, password=password, server=server)
    if not authorized:
        st.write(f"Failed to connect to account #{account_id}. Error code: {mt5.last_error()}")
        return False
    else:
        st.write(f"Successfully connected to account #{account_id}")
        return True

# Step 2: Fetch Account Information
def fetch_account_info():
    account_info = mt5.account_info()
    if account_info is None:
        st.write(f"Failed to fetch account info. Error: {mt5.last_error()}")
    else:
        st.write("### Account Information:")
        account_dict = account_info._asdict()
        for key, value in account_dict.items():
            st.write(f"**{key}**: {value}")

# Step 3: Fetch BTC Price Data from MT5
def fetch_btc_data(symbol, timeframe, num_bars=1000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
    if rates is None:
        st.write(f"Failed to fetch rates for {symbol} with timeframe {timeframe}.")
        return pd.DataFrame()
    btc_data = pd.DataFrame(rates)
    btc_data['time'] = pd.to_datetime(btc_data['time'], unit='s')
    btc_data.set_index('time', inplace=True)
    return btc_data

# Step 4: Feature Engineering
def feature_engineering(btc_data):
    btc_data['Pct_Change'] = btc_data['close'].pct_change() * 100
    btc_data['Class'] = np.where(btc_data['Pct_Change'] > 0, 'U', 'D') 
    btc_data = btc_data.dropna()
    return btc_data

# Step 5: Create New Data Points
def create_new_data_point(btc_data, num_candles=10):
    return btc_data['Pct_Change'].tail(num_candles).values.flatten()

# Step 6: KNN Trading Signal
def knn_trading_signal(btc_data, num_candles=10):
    X = []
    y = []
    for i in range(num_candles, len(btc_data)):
        X.append(btc_data['Pct_Change'].iloc[i - num_candles:i].values)
        y.append(btc_data['Class'].iloc[i])

    X = np.array(X)
    y = np.array(y)
    
    if len(X) < 1:
        st.error("Not enough data to generate signals. Please fetch more data.")
        return None
    
    try:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    except ValueError as e:
        st.error(f"Error during train-test split: {e}")
        return None
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(X_train_scaled, y_train)
    
    new_data_point = create_new_data_point(btc_data, num_candles=num_candles)
    new_data_point_scaled = scaler.transform([new_data_point])
    
    signal = knn.predict(new_data_point_scaled)
    
    return signal[0]

# Step 7: Execute Trade with User-Defined Lot Size
def execute_trade(symbol, action, lot_size):
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        st.write(f"Symbol {symbol} not found.")
        return None

    price = mt5.symbol_info_tick(symbol).ask if action == 'U' else mt5.symbol_info_tick(symbol).bid
    take_profit = price + 0.00010 if action == 'U' else price - 0.00010
    
    order_type = 0 if action == 'U' else 1  # 0 for Buy, 1 for Sell
    comment = "KNN Buy Order" if action == 'U' else "KNN Sell Order"
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "tp": take_profit,
        "deviation": 20,
        "magic": 234000,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        st.write(f"Trade failed: {result.retcode}")
    else:
        trade_details = {
            'symbol': symbol,
            'action': action,
            'price': price,
            'take_profit': take_profit,
            'lot_size': lot_size,
            'status': "Executed"
        }
        # Append executed trade to the session state for history tracking
        st.session_state.trade_history.append(trade_details)
        st.write(f"Trade executed: {comment} at price {price} with TP {take_profit}")
        st.experimental_rerun()  # Trigger a rerun to update the display of executed trades
    return result

# Step 8: Continuous Trading
def continuous_trading(ticker, interval, num_candles, lot_size):
    timeframe_mapping = {
        "M1": (mt5.TIMEFRAME_M1, 60),
        "M5": (mt5.TIMEFRAME_M5, 300),
        "M15": (mt5.TIMEFRAME_M15, 900),
        "H1": (mt5.TIMEFRAME_H1, 3600),
        "D1": (mt5.TIMEFRAME_D1, 86400),
    }
    
    mt5_timeframe, sleep_duration = timeframe_mapping[interval]

    st.write(f"Starting continuous trading for {ticker} with {interval} timeframe.")
    while True:
        btc_data = fetch_btc_data(ticker, mt5_timeframe, num_bars=1000)
        if btc_data.empty:
            st.error("No data fetched. Retrying in the next cycle.")
        else:
            btc_data = feature_engineering(btc_data)
            signal = knn_trading_signal(btc_data, num_candles=num_candles)
            if signal == 'U':
                execute_trade(ticker, 'U', lot_size)
            elif signal == 'D':
                execute_trade(ticker, 'D', lot_size)
            else:
                st.write("No trading signal generated.")
        
        st.write(f"Waiting {sleep_duration // 60} minutes before the next cycle...")
        time.sleep(sleep_duration)

# Step 9: Main Streamlit Interface
def main():
    st.title("KNN Trading Strategy with MetaTrader 5 Integration")

    st.sidebar.header("MetaTrader 5 Account Credentials")
    account_id = st.sidebar.number_input("MT5 Account ID", value=123456789)
    password = st.sidebar.text_input("MT5 Password", type="password")
    server = st.sidebar.text_input("MT5 Server", value="MetaQuotes-Demo")

    st.sidebar.header("Trading Parameters")
    ticker = st.sidebar.text_input("Ticker", value="BTCUSD")
    interval = st.sidebar.selectbox("Data Interval", ["M1", "M5", "M15", "H1", "D1"], index=2)
    num_candles = st.sidebar.number_input("Number of Candles for Prediction", value=10, min_value=5)
    lot_size = st.sidebar.number_input("Lot Size", value=0.1, min_value=0.01, step=0.01)

    if st.sidebar.button("Connect to MetaTrader 5"):
        if connect_mt5(account_id, password, server):
            st.write("Connected successfully.")
            fetch_account_info()

    if st.sidebar.button("Start Continuous Trading"):
        # Start a new thread for continuous trading to allow the UI to remain responsive
        trading_thread = threading.Thread(target=continuous_trading, args=(ticker, interval, num_candles, lot_size))
        trading_thread.start()

    if st.sidebar.button("Shutdown MetaTrader 5"):
        mt5.shutdown()
        st.write("Disconnected from MetaTrader 5")

    # Display the executed trades
    if st.session_state.trade_history:
        st.write("### Executed Trades:")
        trade_df = pd.DataFrame(st.session_state.trade_history)
        st.dataframe(trade_df)

if __name__ == "__main__":
    main()




# ................................. HOW TO RUN THE APP ...............................................

#   cd C:\Users\User\Desktop\mt5_streamlit_project

#   streamlit run app.py
