# task_cal_app_sim_matrix.py

from celery_app import app
from utils.connect import _db_connect
from utils.connect import get_engine
import math
import pandas as pd
import time
import json
import os
from operator import itemgetter
from celery.utils.log import get_task_logger
import datetime
import pytz
import yaml
import gc
import sys

logger = get_task_logger('myapp')

with open(os.path.join('/app-recommend/config/', 'config_{}.yaml'.format(os.environ['RUN_ENV']))) as F_HANDLE:
    CONFIG_FILE = yaml.load(F_HANDLE, Loader=yaml.FullLoader)


@app.task(bind=True, max_retries=0, ignore_result=True)
def cal_sim_matrix(self):
    database_name = CONFIG_FILE['DATABASE']['DATABASE_NAME']
    table_name = CONFIG_FILE['DATABASE']['CAL_TABLE_NAME']
    # limit = 100000
    engine = get_engine(database_name)
    # query_sql = "SELECT * FROM public.{}".format(table_name)
    query_sql = "SELECT * FROM public.{}".format(table_name)
    data = pd.read_sql(query_sql, con=engine)
    print(sys.getsizeof(data))
    if len(data) < 2500000:
        print('Data update ERROR !')
    # 机型列表(非机器上报数据，机器上报机型见mgt平台)
    # model_v_list = ['V2_PRO', 'V2', 'V1s', 'V1', 'V2s']
    # model_l_list = ['L2', 'L2K', 'L2s']
    # model_p_list = ['P1_4G', 'P1N', 'P2', 'P2_PRO', 'P2lite', 'P1', 'P2mini']
    # model_T_list = ['T1', 'T2', 'T2mini', 'T2lite', 'T2mini_s', 'T1mini', 'T2s_LITE', 'T2s']
    # model_D_list = ['D1', 'D2', 'D1s', 'D2s', 'D2_d', 'D1s_d', 'D2mini', 'D2s_LITE']
    # publish_3_list = ['[3]', '[2,3]', '[2]', '[3,2]']
    # data = data[data['model_v_list'].isin(model_v_list)]
    else:
        data = data[data['aid'].notna()]
        publish_3_list = ['[3]', '[2,3]', '[2]', '[3,2]']  # 该列表表示app未在大陆市场发布
        data = data[~data['publisharea'].isin(publish_3_list)]  # 去除未在大陆市场发布app的记录数据
        for model in CONFIG_FILE['MODEL_LIST']['LIST']:
            dataSet = {}
            if model == 'ALL':
                data_remain = data
            else:
                data_remain_list = CONFIG_FILE['MODEL_LIST'][model]
                data_remain = data[data['model'].isin(data_remain_list)]  # 保留对应机型的记录数据
            for i in data_remain.axes[0]:
                user = data_remain.msn[i]
                app = data_remain.aid[i]
                rating = data_remain.ucount[i]
                dataSet.setdefault(user, {})
                dataSet[user][app] = rating
            print('Successfully ! ')

            app_popular = {}
            app_sim_matrix = {}

            for user, apps in dataSet.items():
                for app in apps:
                    if app not in app_popular:
                        app_popular[app] = 0
                    app_popular[app] += 1

            app_count = len(app_popular)
            print("Total app number = %d" % app_count)

            for user, apps in dataSet.items():
                for app1 in apps:
                    app_sim_matrix.setdefault(app1, {})
                    for app2 in apps:
                        if app1 == app2:
                            continue
                        app_sim_matrix[app1].setdefault(app2, 0)
                        app_sim_matrix[app1][app2] += 1
            print("Build co-rated users matrix success!")

            print("Calculating app similarity matrix ...")
            for app1, related_apps in app_sim_matrix.items():
                for app2, count in related_apps.items():
                    if app_popular[app1] == 0 or app_popular[app2] == 0:
                        app_sim_matrix[app1][app2] = 0
                    else:
                        app_sim_matrix[app1][app2] = count / math.sqrt(app_popular[app1] * app_popular[app2])
            print('Calculate app similarity matrix success!')

            FILE_PATH = CONFIG_FILE['SAVE_PATH']
            with open(os.path.join(FILE_PATH, 'app_sim_matrix_{}.json'.format(model)), 'w') as file_obj:
                json.dump(app_sim_matrix, file_obj)
            print('Save successfully !')

            print(os.path.join(FILE_PATH, 'app_sim_matrix_{}.json'.format(model)))

            print(sys.getsizeof(dataSet))
            del dataSet
            gc.collect()
            print('Del successfully')


'''
@app.task(bind=True, max_retries=0, ignore_result=True)
def cal_sim_matrix(self):
    a = 1
    print(a)
    time.sleep(60)
    del a
    gc.collect()
    print('del successfully!')
    '''


