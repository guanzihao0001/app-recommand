from connect import _db_connect
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
        self.testSet = {}

        trainSet_len = 0
        testSet_len = 0
        for i in data.axes[0]:
            user = data.msn[i]
            app = data.aid[i]
            rating = data.ucount[i]
            self.trainSet.setdefault(user, {})
            # self.testSet.setdefault(user, {})
            # if len(self.trainSet[user]) == 0:
            self.trainSet[user][app] = rating
            trainSet_len += 1
            # else:
            #     if len(self.testSet[user]) == 0:
            #         self.testSet[user][app] = rating
            #         testSet_len += 1
            #     else:
            #         if random.random() < pivot:
            #             self.trainSet[user][app] = rating
            #             trainSet_len += 1
            #         else:
            #             self.testSet[user][app] = rating
            #             testSet_len += 1
        print('Split trainingSet and testSet success!')
        print('TrainSet = %s' % trainSet_len)
        print('TestSet = %s' % testSet_len)

    # 计算应用之间的相似度
    def calc_app_sim(self, K, N):
        self.n_sim_app = K
        self.n_rec_app = N
        print('Similar app number = %d' % self.n_sim_app)
        print('Recommneded app number = %d' % self.n_rec_app)
        for user, apps in self.trainSet.items():
            for app in apps:
                if app not in self.app_popular:
                    self.app_popular[app] = 0
                    self.app_aidlist.append(app)
                self.app_popular[app] += 1

        self.app_count = len(self.app_popular)
        print("Total app number = %d" % self.app_count)

        for user, apps in self.trainSet.items():
            for app1 in apps:
                self.app_sim_matrix.setdefault(app1, {})
                for app2 in apps:
                    if app1 == app2:
                        continue
                    self.app_sim_matrix[app1].setdefault(app2, 0)
                    self.app_sim_matrix[app1][app2] += 1
        print("Build co-rated users matrix success!")

        # 计算应用之间的相似性
        print("Calculating app similarity matrix ...")
        for app1, related_apps in self.app_sim_matrix.items():
            for app2, count in related_apps.items():
                # 注意0向量的处理，即某应用的用户数为0
                if self.app_popular[app1] == 0 or self.app_popular[app2] == 0:
                    self.app_sim_matrix[app1][app2] = 0
                else:
                    self.app_sim_matrix[app1][app2] = count / math.sqrt(self.app_popular[app1] * self.app_popular[app2])
        print('Calculate app similarity matrix success!')

        return self.app_sim_matrix, self.app_aidlist

    def recommend2(self, user):
        K = self.n_sim_app
        N = self.n_rec_app
        rank = {}
        watched_apps = self.trainSet[user]
        for app, rating in watched_apps.items():
            if app not in self.app_sim_matrix:
                continue
                # break
            else:
                for related_app, w in sorted(self.app_sim_matrix[app].items(), key=itemgetter(1), reverse=True)[:K]:
                    if w != 0:
                        if related_app in watched_apps:
                            continue
                        rank.setdefault(related_app, 0)
                        rank[related_app] += w * float(rating)
                    else:
                        continue
        return sorted(rank.items(), key=itemgetter(1), reverse=True)[:N]

    # 产生推荐并通过准确率、召回率和覆盖率进行评估
    def evaluate(self, K, N, sim_matrix, new_applist, old_applist):
        self.n_sim_app = K
        self.n_rec_app = N
        self.app_sim_matrix = sim_matrix
        self.app_popular = {}
        self.app_aidlist = []

        print('Similar app number = %d' % self.n_sim_app)
        print('Recommneded app number = %d' % self.n_rec_app)

        i = 0
        for user, apps in self.trainSet.items():

            for app in apps:
                if app not in self.app_popular:
                    self.app_popular[app] = 0
                    self.app_aidlist.append(app)
                self.app_popular[app] += 1

            i += 1
            if i % 100000 == 0:
                print(i)

        self.app_count = len(self.app_popular)

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
        diversity = 0
        for i, user in enumerate(self.trainSet):
            div = 0
            if i % 10 !=0:continue
            if i % 100 ==0:print(i)
            if i >= 160000: break
            tp = list(new_applist[(new_applist["msn"] == user)]["applist"])
            tp_old = list(old_applist[(old_applist["msn"] == user)]["applist"])
            if len(tp_old) != 0:
                old_apps = list(map(int, tp_old[0].split(",")))
            else:
                continue
            if len(tp) != 0:
                test_apps = list(map(int, tp[0].split(",")))
            else:
                continue
            rec_apps = self.recommend2(user)
            # if i % 100 == 0:
            #     print(i)
            self.rec_list.append(rec_apps)
            for app, w in rec_apps:
                for app2, k in rec_apps:
                    if app == app2:
                        continue
                    else:
                        try:
                            div = div + float(sim_matrix[app][app2])
                        except KeyError:
                            continue
                if (app in test_apps) and (app not in old_apps):
                # if app in test_apps:
                    hit += 1
                all_rec_apps.add(app)
            if len(test_apps) != 0:
                rec_count += N
            # rec_count += len(rec_apps)
            test_count += len(test_apps)
            test_count -= len(old_apps)
            j += 1
            if j % 100000 == 0:
                print(j)
            diver = 1 - div / (N * (N - 1))
            diversity = diversity + diver
        diversity = diversity / j
        for i in range(len(self.rec_list)):
            rec_count_adj += len(self.rec_list[i])
        print(rec_count, rec_count_adj, test_count, self.app_count)
        if rec_count == 0 or rec_count_adj == 0 or test_count == 0 or self.app_count == 0:
            print('Insufficient data!')
            return 0, 0, 0, 0

        else:
            print("hit=%d" % hit)
            precision = hit / (1.0 * rec_count)
            precision_adj = hit / (1.0 * rec_count_adj)
            recall = hit / (1.0 * test_count)
            coverage = len(all_rec_apps) / (1.0 * self.app_count)
            print('precisioin=%.4f\tprecision_adj=%.4f\nrecall=%.4f\ncoverage=%.4f\ndiversity=%.4f'
                  % (precision, precision_adj, recall, coverage, diversity))
            return precision, precision_adj, recall, coverage, diversity


if __name__ == '__main__':
    # arg1, arg2 = sys.argv[1], sys.argv[2]
    model, N = sys.argv[1], sys.argv[2]
    log = Logger('eval.log', level='debug')
    try:
        N = int(N)
    except ValueError as e:
        log.logger.error('The second parameter is not an integer'.format(N))
        N = 20
    start_time = time.time()
    os.environ['RUN_ENV'] = 'onl'
    with open(os.path.join('/Users/sm2595/app-recommend/config/',
                           'config_{}.yaml'.format(os.environ['RUN_ENV']))) as F_HANDLE:
        CONFIG_FILE = yaml.load(F_HANDLE, Loader=yaml.FullLoader)
    if model not in CONFIG_FILE['MODEL_LIST']:
        log.logger.error('Unable to find {} in model list'.format(model))
        model = 'ALL'

    database_name = CONFIG_FILE['DATABASE']['DATABASE_NAME']
    table_name = CONFIG_FILE['DATABASE']['RECOMMEND_TABLE_NAME']
    # limit = 100000
    engine = get_engine(database_name)
    # print("11")
    dfold = pd.read_csv("../data_for_eval/applist_211216_2022_03_03.csv", usecols=[1, 2])
    df = pd.read_csv("../data_for_eval/msn_applist_2022_02_28.csv", usecols=[1, 2])
    # query_sql = "SELECT * FROM public.{}".format(table_name)
    # query_sql = "SELECT * FROM public.{} ".format(table_name)
    # data = pd.read_sql(query_sql, con=engine)
    data1 = pd.read_csv("/Users/sm2595/app-recommend/celery_app/ads_ai_app_usedtime_1m.csv")
    data2 = pd.read_csv("/Users/sm2595/app-recommend/celery_app/ads_ai_app_usedtime_1m1.csv")
    data3 = pd.read_csv("/Users/sm2595/app-recommend/celery_app/ads_ai_app_usedtime_1m2.csv")
    data=data1
    #data = pd.read_csv("file3.csv")
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

    precision, recall, coverage, precision_adj, diversity = 0, 0, 0, 0, 0
    itemCF_test.get_dataset(data, pivot=1)
    print(itemCF_test.trainSet)
    # print("trainset")
    # print(itemCF_test.trainSet["VS0518BH51920"])
    # itemCF_test.sampleamount(200000)

    "！！！！！！！！！！！！！！！！！！！！！！！！！"
    app_sim_matrix, app_aidlist = itemCF_test.calc_app_sim(40, 20)
    # print(app_sim_matrix[6878.0][906])
    FILE_PATH = CONFIG_FILE['SAVE_PATH']
    with open(os.path.join("/Users/sm2595/app-recommend/", 'app_sim_matrix_test.json'), 'w') as file_obj:
        json.dump(app_sim_matrix, file_obj)
    print('Save successfully !')
    # print(len(app_sim_matrix))
    # print(itemCF_test.recommend2(user="VS0518BH51920"))
    precision, precision_adj, recall, coverage, diversity = itemCF_test.evaluate(40, N, app_sim_matrix, df, dfold)
    precision_list.append(precision)
    recall_list.append(recall)
    coverage_list.append(coverage)

    print(precision, recall)
    if precision == 0 and recall == 0:
        log.logger.info('Insufficient data for this model type!')
    else:
        log.logger.info(
            'model: {}, recommend app number: {}, precision: {}, recall: {}, precision_adj: {}, coverage: {}, diversity: {}'.format(
                model, N, precision, recall, precision_adj, coverage, diversity))
