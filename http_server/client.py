import requests
import json
import os
import time
'''params={"msn": "DA0318C373062",
                             "model": "D2",
                             "recommend_num": "10",
                             }'''
if __name__ == '__main__':
    stime = time.time()
    # 调用函数的地址
    url = "http://app-recommend.sunmi.com/app-recommend/api/v1"

    # params传进, msn, 已安装列表aid, 机型, 推荐个数
    r = requests.get(url=url,
                     params={"msn":"VB01D8AW11105",
                             "model":"V2",
                             "recommend_num":"10"
                            }
                     )

    s = json.loads(r.content)
    print(s)
    print(time.time() - stime)
