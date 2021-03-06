#!/bin/sh
set -e

DES=/opt/jenkins/mala/server
ENV=/opt/jenkins/env
SET=/opt/keys-pros

. $ENV/bin/activate
cd $DES

if [ -n "`ps aux | grep gunicorn | grep server.wsgi| awk '{ print $2 }'`" ]
then
    echo 'Restarting gunicorn...'
    ps aux | grep gunicorn | grep server.wsgi| awk '{ print $2 }' | xargs kill -HUP
    echo 'Restarted.'
else
    echo 'Starting gunicorn...'
    gunicorn server.wsgi:application --bind 127.0.0.1:8001 &
    echo 'Started.'
fi

if [ -n "`ps aux | grep celery | grep python | awk '{ print $2 }'`" ]
then
    echo 'Restarting celery...'
    celery multi restart taskman -A server -l info --pidfile=/var/run/celery/%n.pid --beat
    echo 'Restarted.'
else
    echo 'Starting celery...'
    celery multi start taskman -A server -l info -c2 --pidfile=/var/run/celery/%n.pid --beat
    echo 'Started.'
fi
