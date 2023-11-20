#testing pull testest
from datetime import timedelta
from celery.schedules import crontab

broker_url = [
    'pyamqp://rusr:mypassword@rbot1//',
    'pyamqp://rusr:mypassword@rbot2//'
]

result_backend = 'rpc://'
imports = ('celery_rsi', 'celery_close')
accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = 'Asia/Singapore'

beat_schedule = {}
# USD/CHF is 11000/6*13.5
# AUD/SGD is 15000/6*13.5
# AUD/USD is 2343.79/6*13.5

# Define bot configurations
bots = [
    {"name": "bot1_AUDUSD","accountID": "001-003-255162-005","access_token": "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540","currencies": ["AUD_USD"],"lot_size": 5300,"environment": "live","weight": 5,"profit": 5.3},
#    {"name": "bot2_USDCHF","accountID": "001-003-255162-004","access_token": "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540","currencies": ["USD_CHF"],"lot_size": 24750,"environment": "live","weight": 5,"profit": 110},
#    {"name": "bot3_AUDSGD","accountID": "001-003-255162-003","access_token": "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540","currencies": ["AUD_SGD"],"lot_size": 33750,"environment": "live","weight": 5,"profit": 150},  
    {"name": "botgx","accountID": "001-003-134550-004","access_token": "6ff3785ec0bf8e9d3779a70ad70437e8-90b43db3853c48c04ac9a19d395fbe08","currencies": ["AUD_SGD","AUD_USD"],"lot_size": 250,"environment": "live","weight": 5,"profit": 2.3},    
]

# Dynamically generate beat_schedule entries based on bot configurations
for bot in bots:
    bot_name = bot["name"]
    beat_schedule[f'run_{bot_name}_monday'] = {
        'task': 'celery_rsi.run_autotrade',
        'schedule': crontab(minute=0, hour='7-23', day_of_week='mon'),
        'args': (bot["access_token"], bot["accountID"], bot["environment"], bot["currencies"], bot["lot_size"], bot["weight"]),
    }
    beat_schedule[f'run_{bot_name}_tue_to_fri'] = {
        'task': 'celery_rsi.run_autotrade',
        'schedule': crontab(minute=0, hour='0-4,6-23', day_of_week='tue-fri'),
        'args': (bot["access_token"], bot["accountID"], bot["environment"], bot["currencies"], bot["lot_size"], bot["weight"]),
    }
    beat_schedule[f'run_{bot_name}_saturday'] = {
        'task': 'celery_rsi.run_autotrade',
        'schedule': crontab(minute=0, hour='0-4', day_of_week='sat'),
        'args': (bot["access_token"], bot["accountID"], bot["environment"], bot["currencies"], bot["lot_size"], bot["weight"]),
    }
    beat_schedule[f'{bot_name}_close_monday'] = {
        'task': 'celery_close.close_positions',
        'schedule': crontab(minute='*', hour='5-23', day_of_week='mon'),
        'args': (bot["accountID"], bot["access_token"], bot["profit"]),
    }
    beat_schedule[f'{bot_name}_close_tue_to_fri'] = {
        'task': 'celery_close.close_positions',
        'schedule': crontab(minute='*', hour='0-23', day_of_week='tue-fri'),
        'args': (bot["accountID"], bot["access_token"], bot["profit"]),
    }
    beat_schedule[f'{bot_name}_close_saturday'] = {
        'task': 'celery_close.close_positions',
        'schedule': crontab(minute='*', hour='0-5', day_of_week='sat'),
        'args': (bot["accountID"], bot["access_token"], bot["profit"]),
    } 

