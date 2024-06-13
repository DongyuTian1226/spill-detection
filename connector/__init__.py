import os
import requests
import logging
from datetime import datetime

'''Connect the server and algorithms by Kafka.'''


class HttpPoster():
    '''class HttpPoster

    properties
    ----------
    url: str, http上报的url
    用法:
    poster = HttpPoster(url)
    poster.run(data)
    将data上报到url
    '''
    def __init__(self, url, deviceID: str = None, deviceType: int = 0, level=logging.DEBUG):
        '''function __init__

        input
        -----
        url: str, http上报的url
        '''
        self.url = url
        if deviceID is not None:
            self._initHttpLogger(deviceID, deviceType, level)

    def _initHttpLogger(self, deviceID: str, deviceType: int = 200, level=logging.DEBUG):
        self.logger = logging.getLogger(deviceID + '_' + str(deviceType))
        self.logger.setLevel(level)
        fmtStrList = ['asctime', 'name', 'levelname', 'filename', 'message']
        fmtStr = ' - '.join(['%('+i+')s' for i in fmtStrList])
        formatter = logging.Formatter(fmtStr)
        # 控制台日志
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.setLevel(logging.ERROR)
        self.logger.addHandler(ch)
        # 文件日志
        logsDir = './logger/logs'
        if not os.path.exists(logsDir):     # 判断两层文件夹是否存在
            os.mkdir(logsDir)
        deviceDir = f'{logsDir}/{self.logger.name}'
        if not os.path.exists(deviceDir):
            os.mkdir(deviceDir)
        filePath = f'./logger/logs/{deviceID + '_' + str(deviceType)}/' + \
            f'http-{datetime.now().strftime("%Y-%m-%d")}.log'
        fh = logging.FileHandler(filePath, encoding='utf-8')
        fh.setFormatter(formatter)
        fh.setLevel(level)
        self.logger.addHandler(fh)

    def run(self, events: list):
        '''function run

        input
        -----
        events: list, 需要上报的事件列表

        将事件列表中的事件以POST形式上传给http.
        按照协议要求, 逐个上报
        '''
        for event in events:
            self.postData(event)
        pass

    def postData(self, data: dict) -> requests.Response:
        '''function run

        input
        -----
        data: dict, 需要上报的数据

        将字典格式的数据以POST形式上传给http
        '''
        # r = requests.post(self.url, data=data)
        r = requests.post(self.url, json=data)
        self.logger.debug(f"Post data: {data}")
        if r.status_code // 100 != 2:
            print(f"Failed to upload data, status code: {r.status_code}")
            print("Response body:")
            try:
                print(r.json())  # Try to parse the response body as JSON
            except ValueError:
                print(r.text)  # If the response body is not JSON, print it as is
        return r
