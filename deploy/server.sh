#!/bin/bash
DJANGODIR=$(dirname $(cd `dirname $0` && pwd))
echo ".: Directory by project :."
echo $DJANGODIR
DJANGO_SETTINGS_MODULE=admin.settings
cd $DJANGODIR
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
exec python manage.py runserver 0:8029
