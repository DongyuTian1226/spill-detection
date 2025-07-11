import os
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


plt.tight_layout()
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
# plt.rcParams['figure.figsize'] = (12.0, 8.0)
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300


def drawTimespace(data: pd.DataFrame, saveDir: str, suffix: str = '',
                  maxFrameNum: int = 1e20, v_trans: bool = False,
                  laneIndex: int = 2,
                  carIDIndex: int = 1, frameIndex: int = 0,
                  locationIndex: int = 4, vIndex: float = 10):
    '''function drawTimespace

    input
    -----
    data: pd.DataFrame, 数据表
    saveDir: str, 保存图片的文件夹
    maxFrameNum: int, 最大画图的帧数
    laneIndex: int, 车道索引
    carIDIndex: int, 车辆ID索引
    frameIndex: int, 帧索引
    locationIndex: int, 位置索引
    vIndex: int, 速度索引

    return
    ------
    None

    根据一个dataframe, 画出时空轨迹图
    '''
    deviceID = data['deviceID'].iloc[0]
    carID = data['id'].iloc[0]
    colLane, colCarID, colFrame, colLocation, colV = list(
        map(lambda x: data.columns[x],
            [laneIndex, carIDIndex, frameIndex, locationIndex, vIndex]))
    data = data.sort_values(
        by=[colLane, colCarID, colFrame],
        axis=0, ascending=[True, True, True])
    data = data[data[colFrame] < maxFrameNum]   # 只观察前maxFrameNum帧
    data[colV] = data[colV] * 3.6 if v_trans else data[colV]   # 速度单位转换为km/h
    data = data.reset_index(drop=True)
    for lane, laneGroup in data.groupby(data[colLane]):
        plt.figure(figsize=(20, 6))
        for _, carTraj in laneGroup.groupby(laneGroup[colCarID]):
            # 速度取绝对值，以免速度方向与指定方向相反而带有负号
            carTraj[colV] = carTraj[colV].abs()
            plt.scatter(carTraj[colFrame], carTraj[colLocation],
                        c=list(carTraj[colV]), cmap=cm.rainbow_r, s=1)
        plt.title("lane %d" % lane)
        plt.colorbar()
        plt.savefig(saveDir +
                    f"/{deviceID}_id-{carID}_{suffix}_lane-{lane}.jpg",
                    dpi=300)
        plt.close()


singleCarEventTypes = ["stop", "lowSpeed", "highSpeed", "emgcBrake",
                       "illegalOccupation"]
laneEventTypes = ["spill", "crowd"]


def getEventData(excelDf: pd.DataFrame, dataDf: pd.DataFrame, type: str):
    '''function getEventData

    input
    -----
    excelDf: pd.DataFrame, excel事件表, 仅一行数据
    dataDf: pd.DataFrame, 轨迹数据表
    type: str, 事件类别

    return
    ------
    data: pd.DataFrame, 事件相关数据

    根据事件类别获取事件相关数据
    '''
    # 对于单车事件, 直接获取
    if type in singleCarEventTypes:
        return dataDf[dataDf['id'] == int(excelDf['id'])]
    elif type in laneEventTypes:
        return dataDf[dataDf['lane'] == excelDf['start_lane']]
    elif type == "incident":
        carIDs = [int(x) for x in excelDf['id'].split(',')]
        df1 = dataDf[dataDf['id'] == carIDs[0]]
        df2 = dataDf[dataDf['id'] == carIDs[1]]
        return pd.concat([df1, df2])


def drawExcelEventCarIDTrajectory(
        excelPath: str, dataPath: str,
        typeList: list = ['stop', 'incident', 'spill']):
    '''function drawExcelEventCarIDTrajectory

    input
    -----
    excelPath: str, excel事件报警文件路径
    dataPath: str, 轨迹数据文件路径

    return
    ------
    None

    从excel文件中读取数据, 画出指定事件类别的车辆轨迹图
    '''
    # 读取excel文件
    eventDf = pd.read_excel(excelPath)
    dataDf = pd.read_csv(dataPath)
    dataDf['lane'] = dataDf['lane'].apply(lambda x: x - 100 if x > 100 else x)
    imgDirPath = excelPath.replace('.xlsx', '_images').replace(
        '.csv', 'images')
    if not os.path.exists(imgDirPath):
        os.makedirs(imgDirPath)
    # 画图
    for i in range(eventDf.shape[0]):
        type = eventDf['type'].iloc[i]
        if type not in typeList:
            continue
        deviceID = eventDf['deviceID'].iloc[i]
        eventID = eventDf['eventID'].iloc[i]
        eventData = getEventData(eventDf.iloc[i], dataDf, type)
        if len(eventData) == 0:
            print(f'no data for deviceID {deviceID} eventID {eventID}')
            continue
        print(f'drawing deviceID {deviceID} eventID {eventID}')
        startTime = eventData['timestamp'].min() / 1000     # s为单位
        timeStr = time.strftime(
            "%Y-%m-%d %H-%M-%S", time.localtime(startTime))
        drawTimespace(eventData, imgDirPath, suffix=type + '_' + timeStr)


def drawTimespaceIdColor(
        data: pd.DataFrame, saveDir: str, suffix: str,
        maxFrameNum: int = 1e20, v_trans: bool = False,
        laneIndex: int = 2, carIDIndex: int = 1,
        frameIndex: int = 0, locationIndex: int = 4, vIndex: int = 10):
    '''function drawTimespace

    input
    -----
    data: pd.DataFrame, 数据表
    saveDir: str, 保存图片的文件夹
    maxFrameNum: int, 最大画图的帧数
    laneIndex: int, 车道索引
    carIDIndex: int, 车辆ID索引
    frameIndex: int, 帧索引
    locationIndex: int, 位置索引
    vIndex: int, 速度索引

    return
    ------
    None

    根据一个dataframe, 画出时空轨迹图。不同id的color赋予不同颜色
    '''
    idList = data['id'].unique()
    # 每个id随机出一个颜色
    idColor = {id: (np.random.rand(), np.random.rand(), np.random.rand())
               for id in idList}
    deviceID = data['deviceID'].iloc[0]
    carID = data['id'].iloc[0]
    colLane, colCarID, colFrame, colLocation, colV = list(
        map(lambda x: data.columns[x],
            [laneIndex, carIDIndex, frameIndex, locationIndex, vIndex]))
    data = data.sort_values(
        by=[colLane, colCarID, colFrame],
        axis=0, ascending=[True, True, True])
    data = data[data[colFrame] < maxFrameNum]   # 只观察前maxFrameNum帧
    data[colV] = data[colV] * 3.6 if v_trans else data[colV]   # 速度转为km/h
    data = data.reset_index(drop=True)
    for lane, laneGroup in data.groupby(data[colLane]):
        plt.figure(figsize=(20, 6))
        for _, carTraj in laneGroup.groupby(laneGroup[colCarID]):
            # 速度取绝对值，以免速度方向与指定方向相反而带有负号
            carTraj[colV] = carTraj[colV].abs()
            plt.scatter(carTraj[colFrame], carTraj[colLocation],
                        c=[idColor[id] for id in carTraj[colCarID]], s=1)
        plt.title("lane %d" % lane)
        plt.colorbar()
        plt.savefig(saveDir +
                    f"/{deviceID}_id-{carID}_{suffix}_lane-{lane}.jpg",
                    dpi=300)
        plt.close()


if __name__ == "__main__":
    # # # 画出事件车辆的时空轨迹图
    # eventSummaryPath = r'analysis\4月22，23日全天数据\logs.xlsx'
    # dataPathList = [
    #     # r'E:\data\2024-4-22-15.csv',
    #     r'E:\data\2024-4-22-16.csv',
    #     r'E:\data\2024-4-22-17.csv',
    #     r'E:\data\2024-4-23-8.csv',
    #     r'E:\data\2024-4-23-9.csv',
    #     r'E:\data\2024-4-23-13.csv',
    #     r'E:\data\2024-4-23-15.csv',
    #     r'E:\data\2024-4-23-16.csv'
    # ]
    # for dataPath in dataPathList:
    #     drawExcelEventCarIDTrajectory(eventSummaryPath, dataPath,
    #                                 typeList=['stop', 'incident', 'spill'])

    # # 按id分配不同color画ts图
    # dataPath = r'data\extractedData\2024-3-27-17_byDevice\K81+866_1.csv'
    # saveDir = r'data\extractedData\2024-3-27-17_byDevice\K81+866_1_images'
    # data = pd.read_csv(dataPath)
    # # # 全部时长
    # # drawTimespaceIdColor(data, saveDir, 'test')
    # # 10分钟一画, 1小时数据分为6份
    # cutPoints = np.linspace(0, len(data), 7)
    # for i in range(6):
    #     drawTimespaceIdColor(
    #         data[int(cutPoints[i]):int(cutPoints[i+1])],
    #         saveDir, f'_{i}0~{i+1}0min')

    # # 画出指定数据的时空轨迹图
    # dataPathList = [
    #     r'data\extractedData\K81+320_1_start_end.csv'
    # ]
    dataDir = r'D:\myscripts\spill-detection\data\extractedData'
    dataPathList = [os.path.join(dataDir, x) for x
                    in os.listdir(dataDir) if x.endswith('.csv')]
    # TODO 过滤lane
    for dataPath in dataPathList:
        data = pd.read_csv(dataPath)
        saveDir = dataPath.replace('.csv', '_images')
        if not os.path.exists(saveDir):
            os.makedirs(saveDir)
        drawTimespace(data, saveDir)
        print(f'{dataPath} done.')
