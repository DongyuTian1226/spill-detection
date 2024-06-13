import requests
import json


def test():
    # url = 'http://127.0.0.1:5000'
    url = 'http://10.121.25.234:19025/raoyue/seu-events'
    headers = {'Content-Type': 'application/json'}
    data = {
        "type": 1,
        "level": 1,
        "start_time": "2023-12-06 11:11:11",
        "end_time": "2023-12-06 11:11:11",
        "lane": 1,
        "raw_class": 1,
        "point_wgs84": {
            "lat": 33.33,
            "lon": 111.11
            },
        "device_type": 1,
        "device_id": "K99+999"
    }

    r = requests.post(url, headers=headers, data=json.dumps(data))
    # r = requests.post(url, data=data)
    print(r.status_code)
    print(r.text)


if __name__ == '__main__':
    test()