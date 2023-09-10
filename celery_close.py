from oandapyV20 import API
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
from celery import Celery

app = Celery('celery_close')
app.config_from_object('celery_config')

@app.task
def close_positions(accountID, access_token, profit_threshold):
    environments='live'
    api = API(access_token=access_token, environment=environments)

    # Define the maximum trades that can be returned in a single request
    max_count = 500  # update this value according to the API limit

    total_profit = 0.0
    trades_list = []
    count = max_count
    page = 1

    while count == max_count:
        params = {"count": max_count, "page": page}
        r = trades.TradesList(accountID, params)
        api.request(r)
        trade_data = r.response['trades']
        count = len(trade_data)
        trades_list.extend(trade_data)
        total_profit += sum(float(trade['unrealizedPL']) for trade in trade_data)
        page += 1

    print("total profit", total_profit)
    print("profit threshold", profit_threshold)

    # If the total profit is more than the threshold, close all trades
    if total_profit >= profit_threshold:
        # Get the list of open positions
        r = positions.OpenPositions(accountID)
        api.request(r)

        for position in r.response['positions']:
            instrument = position['instrument']
            print('Attempting to close', instrument)

            close_details = {}
            if position['long']['units'] != '0':
                close_details["longUnits"] = "ALL"
            if position['short']['units'] != '0':
                close_details["shortUnits"] = "ALL"

            if close_details:
                # Close the position
                r = positions.PositionClose(accountID, instrument, close_details)
                try:
                    api.request(r)
                    print('Successfully closed', instrument)
                except Exception as e:
                    print('Failed to close', instrument, 'Error:', str(e))
            else:
                print('No open positions to close for', instrument)

