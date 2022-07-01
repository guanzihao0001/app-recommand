from sqlalchemy import create_engine
import time
import pandas as pd
from flask import (
    Flask,
    request,
    jsonify
)
import os
import yaml

PG_SUCCESS = 0
APP = Flask(__name__)

with open(os.path.join('/app-recommend/config/', 'config_{}.yaml'.format(os.environ['RUN_ENV']))) as F_HANDLE:
    CONFIG_FILE = yaml.load(F_HANDLE, Loader=yaml.FullLoader)


def _db_connect(database_name):
    VENDOR = CONFIG_FILE['DB']['VENDOR']
    DRIVER = CONFIG_FILE['DB']['DRIVER']
    USER = CONFIG_FILE['DB']['USER']
    PWD = CONFIG_FILE['DB']['PWD']
    HOST = CONFIG_FILE['DB']['HOST']
    PORT = CONFIG_FILE['DB']['PORT']
    DATABASE = database_name
    conn_str = f"{VENDOR}+{DRIVER}://{USER}:{PWD}" \
               f"@{HOST}:{PORT}/{DATABASE}"
    print('Successfully connected !')
    return create_engine(conn_str)

engines = {}

def get_engine(database_name):
    if not engines.get(database_name, None):
        engines[database_name] = _db_connect(database_name)
    return engines[database_name]


