# gunicorn.conf.py
import os

workers = 1
threads = 1
worker_class = 'sync'
timeout = 300
graceful_timeout = 300
max_requests = 100
max_requests_jitter = 10

# تقليل استخدام الذاكرة
os.environ['PYTHONPATH'] = os.getcwd()