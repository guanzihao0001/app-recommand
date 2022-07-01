import requests
import json
import time


def rec_old(model, user):
    url = "http://192.168.1.41:8001/request"

    payload = {'url': 'https://api.sunmi.com/api/appmarket/app/appmarket/1.0/?service=/getpopularapplist',
               'env': 'RELEASE',
               'site': 'ANDROID',
               'params': '{"machineModel":"model","msn":"user"}'.replace("user", user).replace("model", model)}
    files = [

    ]
    headers = {}

    response = requests.request("POST", url, headers=headers, data=payload, files=files)

    s = json.loads(response.content)
    res = []
    for i in range(len(s["data"])):
        res.append(s["data"][i]["aId"])
    return res


stime = time.time()
print(rec_old( 'M2_MAX', "33"))

print(time.time() - stime)
