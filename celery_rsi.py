import pandas as pd
import time
import warnings
import numpy as np
import concurrent.futures
from oandapyV20.endpoints.pricing import PricingInfo
import pandas_ta as ta
import oandapyV20
from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.orders import OrderCreate
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.positions as positions
from oandapyV20.contrib.requests import PositionCloseRequest
from oandapyV20.endpoints.positions import PositionDetails
from oandapyV20.endpoints.trades import TradesList, TradeClose
from datetime import datetime
import datetime

#access_token = "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540"
#accountID = "001-003-255162-003"
#environments='live'
#client = oandapyV20.API(access_token=access_token, environment=environments)

Ggranularity = 'H1'
#currencies = ["AUD_USD"]
# 9300/8*13.5
#lot_size = 15700
from celery import Celery

app = Celery('celery_rsi')
app.config_from_object('celery_config')

@app.task
def close_position(client, account_id, trade_id):
    # Endpoint to close the trade
    close_trade_endpoint = TradeClose(account_id, trade_id)

    # Close the trade
    try:
        response = client.request(close_trade_endpoint)
        print(f"Successfully closed trade {trade_id}")
    except V20Error as e:
        print(f"Error closing trade: {e}")

def close_all_positions(account_id, access_token, environment, instrument_to_close):
    # Create a client instance   
    client = create_client(access_token, environment)
    # Get all open trades
    params = {"count": 500}  # Use maximum limit as per the API's rules
    trades_endpoint = TradesList(account_id, params)
    response = client.request(trades_endpoint)

    for trade in response["trades"]:
        # If the trade's instrument matches the specified instrument
        if trade["instrument"] == instrument_to_close:
            close_position(client, account_id, trade["id"])




def trade_signal(client, signal, currency, accountID, lot_size):
    current_o_trade = check_num_trades(client, accountID, currency)

    lot_size = lot_size + current_o_trade
    params = {
        "granularity": Ggranularity,
        "count": 1,
        "price": "M",
    }

    bco_data = instruments.InstrumentsCandles(instrument=currency, params=params)
    market_data = client.request(bco_data)['candles'][0]

    market_data['close'] = market_data['mid']['c']
    market_data = pd.DataFrame(market_data, index=[0])
    print(market_data['close'])
    latest_price = float(market_data['close'])
    trailing_stop = str(round(round(latest_price * 0.02, 5) + round(current_o_trade / 100000, 5), 5))

    try:
        order = {
            "order": {
                "units": lot_size,
                "instrument": currency,
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "trailingStopLossOnFill": {
                    "distance": trailing_stop
                }
            }
        }

        if signal == 'buy':
            order['order']['units'] = lot_size # make units positive for buy order
            print("Placing trade: ", order)
            trade = oandapyV20.endpoints.orders.OrderCreate(accountID, data=order)
            response = client.request(trade)
            print("Trade placed: ", response)
        elif signal == 'sell':
            order['order']['units'] = lot_size * -1 # make units negative for sell order
            print("Placing trade: ", order)
            trade = oandapyV20.endpoints.orders.OrderCreate(accountID, data=order)
            response = client.request(trade)
            print("Trade placed: ", response)
        else:
            recommendation = 'hold'
    except oandapyV20.exceptions.V20Error as e:
        print("Error placing trade: ", e)


def get_historical_data(client, instrument, count):
    if count >= 5000:
        paramcount = 5000
    else:
        paramcount = count

    params = {
        "granularity": Ggranularity,
        "count": paramcount,
        "price": "M",
    }

    r = instruments.InstrumentsCandles(instrument=instrument, params=params)
    data = client.request(r)['candles']
    
    # Request the first 5000 candles
    last_timestamp = data[0]["time"]
    loopcount = 0

    while count > 5000:
        loopcount += 1
        count -= 5000

    for i in range(loopcount):
        # Set the "from" parameter to the last timestamp retrieved, if there is one
        if last_timestamp:
            params["to"] = last_timestamp

        # Request the next 5000 candles starting from the last timestamp of the previous request
        r = instruments.InstrumentsCandles(instrument=instrument, params=params)
        response = client.request(r)

        # If there was an error with the request, handle it appropriately
        if "candles" not in response:
            print(f"Error: {response}")
            break

        # Add the new candles to the existing data
        new_data = response["candles"]
        if new_data:
            data = new_data + data
            # Set the last timestamp to the most recent candle retrieved
            last_timestamp = data[0]["time"]
        else:
            # If no new candles were retrieved, we have reached the end of the available data
            break

    # Extract OHLCV data and create a DataFrame for instrument
    df1 = pd.DataFrame([(candle['time'], candle['mid']['o'], candle['mid']['h'], candle['mid']['l'], candle['mid']['c'], candle['volume']) for candle in data],
                       columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df1['time'] = pd.to_datetime(df1['time'])
    df1 = df1.set_index('time')

    df1['close'] = pd.to_numeric(df1['close'])
    return df1


def rsi_strategy(df):
    df['rsi'] = df.ta.rsi(length=4)

    # Check if RSI is below 30 (buy signal)
    if df['rsi'].iloc[-1] <= 30:
        return 'buy'
    # Check if RSI is above 65 (sell signal)
    elif df['rsi'].iloc[-1] >= 65:
        return 'sell'
    else:
        return 'hold'

def check_open_trades(client, account_id, instrument):
    endpoint = positions.OpenPositions(account_id)
    try:
        response = client.request(endpoint)
        for position in response['positions']:
            if position['instrument'] == instrument:
                units = int(position['long']['units']) + int(position['short']['units'])
                if units > 0:
                    return 'buy'
                elif units < 0:
                    return 'sell'
    except V20Error as e:
        print(f"Error retrieving open positions: {e}")

    # No position found for this instrument
    return None

from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.trades import TradesList

def check_num_trades(client, account_id, instrument):
    num_trades = 0
    params = {"count": 500}  # Use maximum limit as per the API's rules
    endpoint = TradesList(account_id, params)
    try:
        response = client.request(endpoint)
        trades = response['trades']
        for trade in trades:
            if trade['instrument'] == instrument:
                num_trades += 1
    except V20Error as e:
        print(f"Error retrieving open trades: {e}")
    return num_trades



def get_spread(client, accountID, currency):
    try:
        pricing_info = PricingInfo(accountID, params={"instruments": currency})
        response = client.request(pricing_info)

        if "prices" in response:
            price = response["prices"][0]
            ask_price = float(price["asks"][0]["price"])
            bid_price = float(price["bids"][0]["price"])
            spread = ask_price - bid_price
            spread_in_pips = spread / 0.0001  # Convert to pips
            return spread_in_pips
        else:
            return None
    except V20Error as e:
        print(f"Error: {e}")
        return None


def create_client(access_token, environment):
    return oandapyV20.API(access_token=access_token, environment=environment)

@app.task
def run_autotrade(access_token, accountID, environment, currencies, lot_size, allow_trade):
    client = create_client(access_token, environment)
    last_timestamp = None

    df = get_historical_data(client, "EUR_USD", 10).add_suffix('_eur')
    latest_timestamp = df.index[-1]

    if last_timestamp is None or latest_timestamp > last_timestamp:
        for currency in currencies:
            last_timestamp = latest_timestamp
            df = get_historical_data(client, currency, 10).add_suffix('_eur')
            action = rsi_strategy(df)

            current_trade = check_open_trades(client, accountID, currency)
            print(latest_timestamp, currency, current_trade)

            if get_spread(client, accountID, currency) < 2:
                print(action)
                if action == 'sell' and current_trade == "buy":
                    close_all_positions(accountID, access_token, environment, currency)
                elif action == 'buy'  and current_trade == "sell":
                    close_all_positions(accountID, access_token, environment, currency)
                
                current_o_trade = check_num_trades(client, accountID, currency)
                print("no. of open trade:", current_o_trade)
                
                if current_o_trade <= allow_trade:
                    trade_signal(client, action, currency, accountID, lot_size)

