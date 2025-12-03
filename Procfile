web: gunicorn subscriptionEngine.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A subscriptionEngine worker --loglevel=info
beat: celery -A subscriptionEngine beat --loglevel=info

