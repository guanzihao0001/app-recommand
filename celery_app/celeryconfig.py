# celeryconfig.py

from datetime import timedelta
import os
from celery.schedules import crontab
import yaml
from kombu import Exchange, Queue
import logging.config

# os.environ['RUN_ENV'] = 'test'
with open(os.path.join('/app-recommend/config/', 'config_{}.yaml'.format(os.environ['RUN_ENV']))) as F_HANDLE:
    CONFIG_FILE = yaml.load(F_HANDLE, Loader=yaml.FullLoader)


BROKER_URL = 'amqp://{0}:{1}@{2}:5672/{3}'.format(
    CONFIG_FILE['AMQP']['AMQP_USER'], CONFIG_FILE['AMQP']['AMQP_PASSWORD'],
    CONFIG_FILE['AMQP']['AMQP_ADDRESS'], CONFIG_FILE['AMQP']['AMQP_VHOST']
)

CELERY_RESULT_BACKEND = "rpc://"
CELERY_IMPORTS = 'celery_app.task_cal_app_sim_matrix'
BROKER_LOGIN_METHOD = 'PLAIN'
BROKER_CONNECTION_RETRY = True
# BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 43200}

CELERY_DEFAULT_EXCHANGE = Exchange('celery', type='direct')
CELERY_QUEUES = (
    Queue('cal_sim_matrix', CELERY_DEFAULT_EXCHANGE, routing_key='cal_sim_matrix'),
)

CELERY_ROUTES = ([('celery_app.task_cal_app_sim_matrix.cal_sim_matrix', {'exchange': 'celery', 'routing_key': 'cal_sim_matrix'}),
                ],)

# CELERY_ROUTES = {'celery_app.task_cal_app_sim_matrix.cal_sim_matrix':  {'queue': 'cal_sim_matrix', "routing_key": "cal_sim_matrix"}}

CELERY_TIMEZONE = 'Asia/Shanghai'


CELERYBEAT_SCHEDULE = {
    'task_cal_app_sim_matrix': {
        'task': 'celery_app.task_cal_app_sim_matrix.cal_sim_matrix',
        # 'schedule': timedelta(seconds=600),
        'schedule': crontab(minute=CONFIG_FILE['CELERY_SCHEDULE']['MINUTE'], hour=CONFIG_FILE['CELERY_SCHEDULE']['HOUR'], day_of_month=CONFIG_FILE['CELERY_SCHEDULE']['DAY_OF_MONTH']),
        # 'schedule': crontab(minute='00,10', hour=16, day_of_month='2'),
        'args': ()
        # 'args':()
    }

}


