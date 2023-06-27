#!/bin/bash

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

. ${PYTHON_VENV_PATH}/bin/activate

export DJANGO_MEDIA_ROOT=${DJANGO_MEDIA_ROOT:-"/opt/mege-data-collector/data/media"}
export DJANGO_STATIC_ROOT=${DJANGO_STATIC_ROOT:-"/opt/mege-data-collector/data/static"}
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-"megedc.settings"}

ACTION=${1:-"appserver-dev"}
ALL_EXEC=""

case "$ACTION" in
    "appserver-dev")
        shift
		ALL_EXEC="./manage.py runserver $APPSERVER_BIND_PORT $@"
        ;;
    "manage.py")
        shift
		ALL_EXEC="./manage.py $@"
        ;;
    "appserver")
        shift
        export GUNICORN_CMD_ARGS=${GUNICORN_CMD_ARGS:-'--bind=0.0.0.0 --access-logfile="-"'}
        django-admin collectstatic --noinput
        django-admin migrate
		ALL_EXEC="gunicorn megedc.wsgi"
        ;;
    "worker")
        shift
        CELERY_WORKER_LOG_LEVEL=${CELERY_WORKER_LOG_LEVEL:-"info"}
        CELERY_WORKER_CONCURRENCY=${CELERY_WORKER_CONCURRENCY:-"2"}
        ALL_EXEC="celery -A megedc.celery worker -l $CELERY_WORKER_LOG_LEVEL --concurrency $CELERY_WORKER_CONCURRENCY $@"
        ;;
    "beat")
        shift
        ALL_EXEC="celery -A megedc.celery beat $@"
        ;;
    *)
        ALL_EXEC="$@"
        ;;
esac

exec $ALL_EXEC