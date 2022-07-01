import os
import pandas as pd
from flask import (
    Flask,
    request
)
from utils.connect import _db_connect
from utils.connect import get_engine
import json
from operator import itemgetter
import datetime
import time
import calendar
from apscheduler.schedulers.background import BackgroundScheduler
import yaml

PG_SUCCESS = 0
APP = Flask(__name__)


loading_matrix = {}
app_sim_matrix = {}

with open(os.path.join('/app-recommend/config/', 'config_{}.yaml'.format(os.environ['RUN_ENV']))) as F_HANDLE:
    CONFIG_FILE = yaml.load(F_HANDLE, Loader=yaml.FullLoader)


@APP.route('/app-recommend/api/v1', methods=['GET'])
def recommend():
    start_time = time.time()
    global app_sim_matrix
    global CONFIG_FILE
    database_name = CONFIG_FILE['DATABASE']['DATABASE_NAME']
    recommend_data_table_name = CONFIG_FILE['DATABASE']['RECOMMEND_TABLE_NAME']
    applist_table_name = CONFIG_FILE['DATABASE']['APPLIST_TABLE_NAME']
    K = CONFIG_FILE['RECOMMEND']['NUMBER_FOR_CALCULATE']

    today = datetime.date.today()
    oneday = datetime.timedelta(days=1)
    m1 = calendar.MONDAY
    while today.weekday() != m1:
        today -= oneday
    lastMonday = today.strftime('%Y-%m-%d')

    msn = request.args.get('msn')
    small_model = request.args.get('model')  # 接收到小机型
    big_model = 0
    for model in CONFIG_FILE['MODEL_LIST']['LIST']:  # 转化为对应大机型
        if small_model in CONFIG_FILE['MODEL_LIST'][model]:
            big_model = model
            break
        else:
            big_model = 'ALL'
    installed_list = []
    # 接受推荐个数相关的参数
    try:
        N = request.args.get('recommend_num', CONFIG_FILE['RECOMMEND']['NUMBER_FOR_RECOMMEND_DEFAULT'], int) # 设置N的默认值
    except ValueError as e:
        N = CONFIG_FILE['RECOMMEND']['NUMBER_FOR_RECOMMEND_DEFAULT']

    if not CONFIG_FILE['RECOMMEND']['NUMBER_FOR_RECOMMEND_MIN'] <= N <= CONFIG_FILE['RECOMMEND']['NUMBER_FOR_RECOMMEND_MAX']:
            N = CONFIG_FILE['RECOMMEND']['NUMBER_FOR_RECOMMEND_DEFAULT']

    connect_start_time = time.time()
    dataSet = {}
    engine = get_engine(database_name)
    # query_sql = "SELECT * FROM public.{} where msn='{}'".format(table_name, msn)
    query_sql = "SELECT * FROM public.{} where date_monday='{}' and msn='{}'".format(recommend_data_table_name, lastMonday, msn)

    data = pd.read_sql(query_sql, con=engine)
    query_sql_applist =  "SELECT * FROM public.{} where msn='{}' order by target_day desc".format(applist_table_name, msn)
    data_applist = pd.read_sql(query_sql_applist, con=engine)
    connect_time = time.time() - connect_start_time
    print('Connection succeeded ! Time = {}'.format(connect_time))
    data = data[data['aid'].notna()]

    rec_dic = {}
    temp_rec_list = []
    if len(data_applist) == 0:
        installed_list = []
    else:
        installed_list = data_applist.applist[0].split(",")

    if len(data) == 0:
        rec_dic['code'] = CONFIG_FILE['STATUS_CODE']['NO_HISTORY_DATA']
        rec_dic['recommended_list'] = temp_rec_list
        rec_dic['msg'] = 'No history data'
    elif not app_sim_matrix:
        rec_dic['code'] = CONFIG_FILE['STATUS_CODE']['NO_APP_SIM_MATRIX']
        rec_dic['recommended_list'] = temp_rec_list
        rec_dic['msg'] = 'No app_sim_matrix'
    else:
        rec_dic['msg'] = 'recommended successfully'
        if big_model == 'ALL':
            rec_dic['code'] = CONFIG_FILE['STATUS_CODE']['NO_MODEL']
            rec_dic['msg'] = 'No model, recommend based on all model data'
        preprocess_start_time = time.time()
        for i in data.axes[0]:
            user = data.msn[i]
            app = str(float(data.aid[i]))
            rating = data.ucount[i]
            dataSet.setdefault(user, {})
            dataSet[user][app] = rating
        print('Data preprocessing succeeded ! Time = {}'.format(time.time() - preprocess_start_time))
        recommend_start_time = time.time()
        rank = {}
        used_apps = dataSet[msn]
        for app, rating in used_apps.items():
            if app not in app_sim_matrix[big_model]:
                continue
                # break
            else:
                for related_app, w in sorted(app_sim_matrix[big_model][app].items(), key=itemgetter(1), reverse=True)[:K]:
                    if w != 0:
                        if related_app in used_apps:
                            continue
                        rank.setdefault(related_app, 0)
                        rank[related_app] += w * float(rating)
                    else:
                        continue
        reclist = sorted(rank.items(), key=itemgetter(1), reverse=True)[:N]
        print(reclist)

        stime = time.time()
        for j in range(len(reclist)):
            if str(int(float(reclist[j][0]))) in installed_list:
                continue
            else:
                temp_app_dic = {}
                temp_app_dic['aid'] = str(int(float(reclist[j][0])))
                temp_app_dic['score'] = reclist[j][1]
                temp_rec_list.append(temp_app_dic)

        rec_dic['code'] = CONFIG_FILE['STATUS_CODE']['OK']
        rec_dic['recommended_list'] = temp_rec_list
        print('Recommended successfully ! Time = {}'.format(time.time() - recommend_start_time))
        print('All time = {}'.format(time.time() - start_time))

    return rec_dic


def tick():
    global loading_matrix
    global app_sim_matrix
    print('tick')
    FILE_PATH = CONFIG_FILE['SAVE_PATH']
    for model in CONFIG_FILE['MODEL_LIST']['LIST']:
        if os.path.exists(os.path.join(FILE_PATH, 'app_sim_matrix_{}.json'.format(model))):
            with open(os.path.join(FILE_PATH, 'app_sim_matrix_{}.json'.format(model)), 'r', encoding='utf8')as fp:
                loading_matrix[model] = json.load(fp)
            app_sim_matrix[model] = loading_matrix[model]
            print('APP similarity matrix for {} loading completed!'.format(model))
        else:
            print('App similarity matrix for {} does not exist !'.format(model))
    return 0

# if __name__ == "__main__":
tick()
scheduler = BackgroundScheduler()
# 每隔5秒执行一次
# scheduler.add_job(tick, 'interval', seconds=30)
# 测试
# scheduler.add_job(tick, 'cron', day='25', hour='13', minute='50,57')
# 每月2号，17号凌晨两点（上海时区）加载新计算得矩阵。
scheduler.add_job(tick, 'cron', day=CONFIG_FILE['LOAD_MATRIX_TASK']['DAY_OF_MONTH'],
                  hour=CONFIG_FILE['LOAD_MATRIX_TASK']['HOUR'], minute=CONFIG_FILE['LOAD_MATRIX_TASK']['MINUTE'])
# 该部分调度是一个独立的线程

scheduler.start()
APP.run()
