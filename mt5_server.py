from flask import Flask, request, jsonify, session
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os

# Setup Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Session encryption key

# Initialize MetaTrader5 for a specific user
def connect_mt5(account_id, password, server):
    print(f"Attempting to connect to MT5 with account: {account_id}, server: {server}")
    
    if not mt5.initialize():
        print("MT5 initialization failed.")
        return jsonify({"status": "error", "message": "MT5 initialization failed."}), 400
    
    authorized = mt5.login(login=account_id, password=password, server=server)
    if not authorized:
        print(f"Failed to connect to account #{account_id}.")
        return jsonify({"status": "error", "message": f"Failed to connect to account #{account_id}."}), 400
    
    # Save the MT5 session to Flask's session storage for the user
    session['mt5_session'] = {
        'account_id': account_id,
        'server': server
    }
    
    print("Connected successfully to MetaTrader5.")
    return jsonify({"status": "success", "message": "Connected to MetaTrader5."}), 200

@app.route("/connect_mt5", methods=["POST"])
def connect_mt5_route():
    data = request.get_json()
    account_id = data.get('account_id')
    password = data.get('password')
    server = data.get('server')

    if not account_id or not password or not server:
        return jsonify({"status": "error", "message": "Missing credentials."}), 400
    
    # Connect to MT5 for this user and store the session
    connection_response = connect_mt5(account_id, password, server)
    
    if connection_response[1] == 200:
        return connection_response
    else:
        return connection_response

@app.route("/fetch_btc_data", methods=["GET"])
def fetch_btc_data():
    # Check if user is connected
    if 'mt5_session' not in session:
        return jsonify({"status": "error", "message": "User not connected to MT5."}), 400

    symbol = request.args.get("symbol", "BTCUSD")
    timeframe = int(request.args.get("timeframe", 5))  # Default M5
    num_bars = int(request.args.get("num_bars", 1000))

    print(f"Fetching data for {symbol} with timeframe {timeframe} and {num_bars} bars")

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
    if rates is None:
        print(f"Failed to fetch rates for {symbol}.")
        return jsonify({"status": "error", "message": "Failed to fetch rates."}), 400
    
    btc_data = pd.DataFrame(rates)
    btc_data['time'] = pd.to_datetime(btc_data['time'], unit='s')
    btc_data.set_index('time', inplace=True)
    
    print(f"Successfully fetched data for {symbol}.")
    return btc_data.to_json(date_format='iso')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)



# ......................... HOW TO RUN THE FLASK ........................................


#1 cd C:\Users\User\Desktop\mt5_streamlit_project

#2  python mt5_server.py

#3 http://127.0.0.1:5000

#  git clone https://github.com/DataScienceCoach/HerokuRobo.git
# 

# cd C:\Users\User\Desktop\Hero\HerokuRobo
# heroku create hrobo1
# git remote add heroku https://git.heroku.com/hrobo1.git

# https://hrobo1.herokuapp.com

