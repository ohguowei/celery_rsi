import time
import warnings
from datetime import datetime
import logging
import pandas as pd
import pandas_ta as ta
import numpy as np
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.positions as positions
from oandapyV20.endpoints.pricing import PricingInfo
from oandapyV20.endpoints.positions import PositionDetails
from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.orders import OrderCreate
from oandapyV20.contrib.requests import PositionCloseRequest
from oandapyV20.endpoints.trades import TradesList, TradeClose

from celery import Celery

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Ggranularity = 'H1'

app = Celery('celery_rsi')
app.config_from_object('celery_config')

def close_position(client, account_id, trade_id):
    close_trade_endpoint = TradeClose(account_id, trade_id)
    api_call(client, close_trade_endpoint)
    logger.info(f"Successfully closed trade {trade_id}")

def close_all_positions(client, account_id, instrument_to_close):
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



def check_open_trades(client, account_id, instrument):
    endpoint = positions.OpenPositions(account_id)
    response = api_call(client, endpoint)
    for position in response['positions']:
        if position['instrument'] == instrument:
            units = int(position['long']['units']) + int(position['short']['units'])
            return 'buy' if units > 0 else 'sell'
    return None

def check_num_trades(client, account_id, instrument):
    params = {"count": 500}
    endpoint = TradesList(account_id, params)
    response = api_call(client, endpoint)
    return sum(trade['instrument'] == instrument for trade in response['trades'])

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

def api_call(client, endpoint):
    try:
        return client.request(endpoint)
    except V20Error as e:
        logger.error(f"API Error: {e}")
        raise

def create_client(access_token, environment):
    return oandapyV20.API(access_token=access_token, environment=environment)

def fetch_and_process_data(client, currency, accountID, lot_size, allow_trade): 
    # Check the number of currently open positions
    current_o_trade = check_num_trades(client, accountID, currency)
    
    # Calculate the number of bars needed for RSI condition based on the number of open positions
    bars_open = 2
    bars_close = 1
    # Fetch enough historical data to check RSI condition
    df = get_historical_data(client, currency, 100).add_suffix('_eur')
    
    action_open,action_close = rsi_strategy(df, bars_open, bars_close)
    current_trade = check_open_trades(client, accountID, currency)

    spread = get_spread(client, accountID, currency)
    if spread is not None and spread < 2.2:
        if action_close != current_trade and action_close in ['buy', 'sell'] and current_trade in ['buy', 'sell']:
          #print("closeall")
          close_all_positions(client,accountID,currency)
          current_o_trade = 0
          action_open = action_close
        if current_o_trade <= allow_trade and action_open in ['buy', 'sell']:
          #print("opentrade")
          trade_signal(client, action_open, currency, accountID, lot_size)

def rsi_strategy(df, bars_open_needed,bars_close_needed):
    # Calculate RSI
    df['rsi'] = df.ta.rsi(length=4)
    # Check if the last 'bars_needed' RSI values are below 30 (buy signal)
    if all(df['rsi'].iloc[-bars_open_needed:] <= 30):
        action_open = 'buy'
    # Check if the last 'bars_needed' RSI values are above 65 (sell signal)
    elif all(df['rsi'].iloc[-bars_open_needed:] >= 65):
        action_open = 'sell'
    else:
        action_open = 'hold'

    # Check if the last 'bars_needed' RSI values are below 30 (buy signal)
    if all(df['rsi'].iloc[-bars_close_needed:] <= 30):
        action_close = 'buy'
    # Check if the last 'bars_needed' RSI values are above 65 (sell signal)
    elif all(df['rsi'].iloc[-bars_close_needed:] >= 65):
        action_close = 'sell'
    else:
        action_close = 'hold'

    return action_open, action_close

@app.task
def run_autotrade(access_token, accountID, environment, currencies, lot_size, allow_trade):
    client = create_client(access_token, environment)

    with ThreadPoolExecutor() as executor:
      futures = [executor.submit(fetch_and_process_data, client, currency, accountID, lot_size, allow_trade) for currency in currencies]
      for future in concurrent.futures.as_completed(futures):
        try:
          future.result()
        except Exception as e:
          logger.error(f"An error occurred: {e}")
