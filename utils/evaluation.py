from connect import get_engine
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
import random
import logging
from logging import handlers
import sys
from rec import rec_old

class Logger(object):
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }  # 日志关系映射

    def __init__(self, filename, level='info', backCount=10,
                 fmt='%(asctime)s -  %(levelname)s: %(message)s'):
        self.logger = logging.getLogger(filename)
        format_str = logging.Formatter(fmt)  # 设置日志格式
        self.logger.setLevel(self.level_relations.get(level))  # 设置日志级别

        sh = logging.StreamHandler()  # 往屏幕上输出
        sh.setFormatter(format_str)  # 设置屏幕上显示的格式
        self.logger.addHandler(sh)  # 把对象加到logger里

        fh = handlers.RotatingFileHandler(filename=filename, maxBytes=10485760, backupCount=backCount)  # 按照文件大小分割日志文件
        fh.setLevel(self.level_relations.get(level))
        fh.setFormatter(format_str)  # 设置文件里写入的格式
        self.logger.addHandler(fh)


class ItemBasedCF_test():
    # 初始化参数
    def __init__(self):
        # 将数据集划分为训练集和测试集
        self.modelSet = {}
        self.trainSet = {}
        self.testSet = {}

        # 推荐列表合集
        self.rec_list = []

        # 应用相似度矩阵
        self.app_sim_matrix = {}
        self.app_popular = {}
        self.app_count = 0
        self.app_aidlist = []

        # 找到相似的K个app，为目标用户推荐N个
        self.n_sim_app = 5  # K
        self.n_rec_app = 5  # N

    # 读文件得到“用户-应用”数据
    # 数据分割
    def get_dataset(self, data, pivot=1):
        # 将数据集划分为训练集和测试集
        self.trainSet = {}
        self.modelSet = {}
        self.testSet = {}

        trainSet_len = 0
        testSet_len = 0
        for i in data.axes[0]:
            user = data.msn[i]
            app = data.aid[i]
            # rating = data.ucount[i]
            model = data.model[i]
            self.trainSet.setdefault(user, [])
            self.trainSet[user].append(app)
            self.modelSet.setdefault(user, model)

    def evaluate(self, new_applist, old_applist):

        print('Evaluating start ...')
        N = self.n_rec_app
        # 准确率和召回率
        hit = 0
        rec_count = 0
        test_count = 0
        rec_count_adj = 0

        # 覆盖率
        all_rec_apps = set()
        # 计时
        j = 0
        for user, model in self.modelSet.items():

            if j % 50!= 0:
                j = j + 1
                continue
            tp = list(new_applist[(new_applist["msn"] == user)]["applist"])
            tp_old = list(old_applist[(old_applist["msn"] == user)]["applist"])
            if len(tp) != 0:
                test_apps = list(map(int, tp[0].split(",")))
            else:
                continue
            if len(tp_old) != 0:
                old_apps = list(map(int, tp_old[0].split(",")))
            else:
                continue
            rec_apps = rec_old(model,user)
            self.rec_list.append(rec_apps)
            #print(old_apps, rec_apps, test_apps)
            diff=[]
            for a in test_apps:
                if a not in old_apps:
                    diff.append(a)
            for app in rec_apps:
                app = int(app)
                if app in diff:
                # if app in test_apps:
                    hit += 1
                all_rec_apps.add(app)

            if len(test_apps) != 0:
                rec_count += 20
            # rec_count += len(rec_apps)
            test_count += len(diff)
            print(hit)
            if hit>=10:
                break

        for i in range(len(self.rec_list)):
            rec_count_adj += len(self.rec_list[i])
        print(rec_count, rec_count_adj, test_count, self.app_count)
        if rec_count == 0 or rec_count_adj == 0 or test_count == 0:
            print('Insufficient data!')
            return 0, 0, 0

        else:
            print("hit=%d" % hit)
            precision = hit / (1.0 * rec_count)
            precision_adj = hit / (1.0 * rec_count_adj)
            recall = hit / (1.0 * test_count)
            print('precisioin=%.4f\tprecision_adj=%.4f\nrecall=%.4f'
                  % (precision, precision_adj, recall))
            return precision, precision_adj, recall


if __name__ == '__main__':
    # arg1, arg2 = sys.argv[1], sys.argv[2]
    model, N = sys.argv[1], sys.argv[2]
    log = Logger('eval.log', level='debug')
    # try:
    #     N = int(N)
    # except ValueError as e:
    #     log.logger.error('The second parameter is not an integer'.format(N))
    #     N = 20
    start_time = time.time()
    os.environ['RUN_ENV'] = 'onl'
    with open(os.path.join('/Users/sm2595/app-recommend/config/',
                           'config_{}.yaml'.format(os.environ['RUN_ENV']))) as F_HANDLE:
        CONFIG_FILE = yaml.load(F_HANDLE, Loader=yaml.FullLoader)
    if model not in CONFIG_FILE['MODEL_LIST']:
        log.logger.error('Unable to find {} in model list'.format(model))
        model = 'ALL'

    dfold = pd.read_csv("data_for_eval/applist_211001_2022_03_04.csv", usecols=[1, 2])
    df = pd.read_csv("data_for_eval/applist_211216_2022_03_03.csv", usecols=[1, 2])
    data = pd.read_csv("data_for_eval/000000_0.csv")
    data = data[data['aid'].notna()]
    data = data[data["cid"] == -1]
    print(data.shape)
    if model != 'ALL':
        data_remain_list = CONFIG_FILE['MODEL_LIST'][model]
        data = data[data['model'].isin(data_remain_list)]

    itemCF_test = ItemBasedCF_test()
    precision_list = []
    recall_list = []
    coverage_list = []
    app_sim_matrix = {}
    app_aidlist = []

    precision, recall, precision_adj = 0, 0, 0
    itemCF_test.get_dataset(data, pivot=1)
    precision, precision_adj, recall = itemCF_test.evaluate(df, dfold)
    precision_list.append(precision)
    recall_list.append(recall)

    print(precision, recall)
    if precision == 0 and recall == 0:
        log.logger.info('Insufficient data for this model type!')
    else:
        log.logger.info(
            'model: {}, recommend app number: {}, precision: {}, recall: {}, precision_adj: {}'.format(
                model, N, precision, recall, precision_adj))
