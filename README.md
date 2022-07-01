基于itemCF的应用市场推荐系统
===

# 一. 项目结构
```
.  
.
├── Dockerfile
├── README.md
├── __pycache__
├── celery_app
│   ├── celeryconfig.py
│   └── task_cal_app_sim_matrix.py
├── config
│   ├── config_onl.yaml
│   └── config_test.yaml
├── entrypoint.sh
├── http_server
│   ├── app.py
│   └── client.py
├── logs
├── main.py
├── requirements.txt
├── supervisord.conf
├── tree.txt
└── utils
    ├── connect.py
    └── eval.py
```

# 二. 相似度矩阵计算

## 1. 通过celery定时任务

计算相似度矩阵任务由celery定时实现，基于数据表更新频率（过去三月数据表在每月10号，25号进行更新），定时设置在每月的11号，26号进行计算存储，相似度矩阵存储路径为 /data/app_recommend，挂载在NAS上。

## 2. celery相关指令

启动celery服务
```
celery -A celery_app worker --loglevel=INFO -Q cal_sim_matrix -c 1 --without-gossip
```

启动celery定时任务
```
celery -A celery_app beat -l INFO
```
## 3. 更新加载相似度矩阵

每次重启/重建容器后，都立即加载一次相似度矩阵，并且在执行celery定时任务，计算存储好相似度矩阵后，项目定期更新相似度矩阵，更新时间为每月11号，26号凌晨两点。


# 三. 项目数据相关情况

## 1. 数据表概况
**'ads_ai_app_usedtime_3m'**：该表用于相似度矩阵计算，定时访问，记录了机器过去三个月APP使用情况。

**'ads_ai_app_usedtime_1m'**：该表用于生成推荐列表，实时访问，记录了机器过去一个月APP使用情况。

**'ads_ai_app_msn_applist_nda'**：该表用于追踪用户已安装应用，实时访问。

**所有任务数据都是T+1的。即任务运行时使用的数据最晚的是前一天的数据。**

## 2. 更新调度

**调度通过读写双方约定，人工的版本控制，来保证服务不存在间断。**

**'ads_ai_app_usedtime_3m'**：数据团队每个月10号和25号下午2点运行。同步时先清掉原表，再将数据全部写入。AI团队11号和26号使用。

**'ads_ai_app_usedtime_1m'**：有一个时间字段date_monday。每周日下午2点运行，例如运行时间是2021-12-12(周六)。同步时，先将date_monday小于2021-12-06(周一)的数据删掉。再将新的数据写入，date_monday为2021-12-13(周一)。AI拿当前周周一的数据。

**'ads_ai_app_msn_applist_nda'**：有一个时间字段target_day。每天上午7点运行，例如运行时间是2021-12-12。同步时，先将新数据写入，target_day为2021-12-11，在将target_day小于等于2021-12-10的数据删除。AI通过msn拿数据，然后优先选择target_day大的使用。

## 3. 注意事项
查询连接未断开，无法执行TRUNCATE操作。但可以执行delete操作。
所以每个月10号和25号不要读取ads_ai_app_usedtime_3m，可能导致任务失败。


## 4. 问题追踪
postgre sql delete 不删除索引，导致占用空间大小非常大。（不会，增加到一定程度就不增加了）

# 四. 验证

校验算法有效程度，通过将数据集近似8：2划分训练集测试集，已验证训练集计算得到的相似度矩阵推荐效果（测试集命中情况）
##1. 说明

代码路径：/app-recommend/utils/eval.py

运行指令：需传入机型参数以及推荐个数参数，例如返回全机型，推荐个数为10的结果：
```
python eval.py ALL 10
```
日志输出：/app-recommend/utils/eval.log
##2. 参数选择

参数一：**model**，相似度矩阵对于机型，参考 /config/config_onl.yaml，从如下选择（错误输入默认为 'ALL' ）：
```
  LIST: ['MODEL_V', 'MODEL_L', 'MODEL_P', 'MODEL_T', 'MODEL_D', 'ALL']
 ```

参数二：**N**，推荐个数选择，输入需要为整数（错误输入默认N为20）。

# 五. 推荐
## 1.历史信息获取
历史信息获取需要进行整合，计算某台机器过去一个月内使用该app天数，并将该指标作为交互信息，反应用户对app的偏好程度，在生成推荐列表是作为权重项计算。

## 2.推荐列表构建
机器上传msn，机型信息，搜索历史使用信息，根据相似度加权得分排序返回推荐列表；并搜索已安装列表进行推荐结果去重。

# 六. 配置文件
通过修改配置文件，调整celery任务执行时间，推荐相关参数等。
1. 数据库相关信息：DB、AMQP、DATABASE；
2. celery相关信息：CELERY_SCHEDULE；
3. 存储路径：SAVE_PATH；
4. 矩阵加载：LOAD_MATRIX_TASK；
5. 推荐相关参数：RECOMMEND；
6. 机型列表（根据数据收集类型需要定期更新）：MODEL_LIST；
7. 其他：STATUS_CODE；

# 七.评估部分代码说明
##1. 新版本
代码路径：/app-recommend/utils/changedeval.py

运行指令
```
python changedeval.py ALL 10
```
其中第一个参数为需要评价的机型，第二个参数为对一台机器推荐几个应用

评估数据来源
```python
dfold = pd.read_csv("../data_for_eval/applist_211216_2022_03_03.csv", usecols=[1, 2])
df = pd.read_csv("../data_for_eval/msn_applist_2022_02_28.csv", usecols=[1, 2])
```
推荐系统v1.0设计使用前一个月的数据计算相似度矩阵并进行推荐。为评估效果，选取了12.16日上线前和今年2.28日上线2个半月后的nda数据库表，nda库记录了每台机器历史下载的applist，通过计算这两个表的差即可得到机器在这两个半月期间新下载的app，若新下载的app有一个和推荐列表中的相同，即计作一次hit。

训练数据
```python
data1 = pd.read_csv("/Users/sm2595/app-recommend/celery_app/ads_ai_app_usedtime_1m.csv")
```

训练结果
```
2022-03-04 15:07:44,686 -  INFO: model: ALL, recommend app number: 20, precision: 0.0018161080891384454, recall: 0.3165137614678899, precision_adj: 0.0019119752459243523, coverage: 0.5957018132975151, diversity: 0.912759403876431
```
主要评估指标：

准确率：描述推荐列表中有多少比例是在新的两个半月时间下载的,即hit/推荐列表长度

召回率：描述两个半月时间里新下载的app有多少是根据推荐列表下载的，即hit/新下载app个数

覆盖率：推荐的app种类个数占相似度矩阵中总共出现过的app个数

多样性：多样性描述了推荐列表中物品两两之间的不相似性。
##2.旧版本

代码路径：/app-recommend/utils/evaluation.py

运行指令
```
python evaluation.py ALL
```
输入要评价的机型，会返回对每个机器推荐20个应用的评估

评估数据来源
```python
dfold = pd.read_csv("data_for_eval/applist_211001_2022_03_04.csv", usecols=[1, 2])
df = pd.read_csv("data_for_eval/applist_211216_2022_03_03.csv", usecols=[1, 2])
data = pd.read_csv("data_for_eval/000000_0.csv")
```
作为对比，同样选取2个半月时段的两份数据，2021年3月15日到6月1日，2021年10月1日到-12月16日，两段时期的nda表，由于nda表没有机器msn号对应的的机型号，所以选取data作为生成旧版推荐列表的数据来源，data为去年3月到6月之间三个月有下载数据的机器，基本可以包含所有活跃的机器。同理也是根据两段时期的nda表，若这段时期新下载的app和原固定推荐列表有一个相同，即计作一次hit。

运行结果
```
2022-03-04 15:27:56,249 -  INFO: model: ALL, recommend app number: 20, precision: 0.0006617257808364214, recall: 0.036390101892285295, precision_adj: 0.0007352508675960238
2022-03-04 16:16:56,745 -  INFO: model: ALL, recommend app number: 20, precision: 0.0005537098560354374, recall: 0.03861003861003861, precision_adj: 0.0006152331733727083
```