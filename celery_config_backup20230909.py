# celery_config.py
from datetime import timedelta

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

beat_schedule = {
    'bot1_audusd_close': {
        'task': 'celery_close.close_positions',
        'schedule': timedelta(minutes=1),
        'args': ("001-003-255162-005", "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540", 93),
    },
    'bot2_usdchf_close': {
        'task': 'celery_close.close_positions',
        'schedule': timedelta(minutes=1),
        'args': ("001-003-255162-004", "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540", 93),
    },
    'bot3_audsgd_close': {
        'task': 'celery_close.close_positions',
        'schedule': timedelta(minutes=1),
        'args': ("001-003-255162-003", "c33734921cd0b7b68c721fc18e2019c2-8cfd11c75b7df0c81301e2cf58846540", 93),
    },
    'botgx_close_all': {
        'task': 'celery_close.close_positions',
        'schedule': timedelta(minutes=1),
        'args': ("001-003-134550-004", "6ff3785ec0bf8e9d3779a70ad70437e8-90b43db3853c48c04ac9a19d395fbe08", 2.5),
    },	
}

