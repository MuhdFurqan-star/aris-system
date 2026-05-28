web: python manage.py migrate --no-input && python manage.py collectstatic --no-input && gunicorn replacement_system.wsgi:application --bind 0.0.0.0:$PORT --workers 2
