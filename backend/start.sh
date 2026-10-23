#!/bin/sh
# Container entrypoint: bring the schema and cache table up to date, then serve.
# Runs on every start because the free Render plan has no pre-deploy hook; both are idempotent.
set -e
python manage.py migrate --noinput
python manage.py createcachetable
exec gunicorn config.wsgi -c gunicorn.conf.py
