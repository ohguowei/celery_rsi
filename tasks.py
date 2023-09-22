from celery import Celery

app = Celery('tasks')
app.config_from_object('celery_config')

# Import the tasks to ensure they're registered
from celery_close import close_positions
from celery_rsi import run_autotrade
from celery_rsi_new import run_autotrade_new

print("Loaded task configuration!")

