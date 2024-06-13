import yaml
import numpy as np
from road_calibration.algorithms import (
    dbi, calQuartiles, poly2fit, poly2fitFrozen, cutPts)


class Calibrator():
    '''class Calibrator

    properties
    ----------
    xyByLane: dict
        按lane存储xy。
    vxyCount: dict
        存储所有vxy的正负计数, 每一次x/y对应的正速度+1, 负速度-1。
    calibration: dict
        存储标定结果。包括: 应急车道号, 车道线方程, 元胞划分直线方程, 合流元胞编号。

    methods
    -------
    run(msg)
        接受每帧传输来的目标信息, 更新给calibrator
    calibrate()
        根据存储的数据计算标定结果。
    save(path)
        将标定结果保存到path。

    生成标定器, 用于标定检测区域的有效行驶片区和应急车道。
    '''

    def __init__(self, clbPath: str, fps: float,
                 laneWidth: float = 3.75, emgcWidth: float = 3.5,
                 cellLen: float = 50.0, qMerge: float = 0):
        '''class function __init__

        input
        ----------
        clbPath: str
            标定结果保存路径。
        fps: float
            帧率。
        laneWidth: float
            车道宽度。
        emgcWidth: float
            应急车道宽度。
        cellLen: float
            元胞长度。
        qMerge: float
            判定元胞为合流区域的流量, 小于qMerge判定该cell不可用。

        生成标定器, 用于标定检测区域的有效行驶片区和应急车道。
        '''
        # 初始化属性
        self.clbPath = clbPath                  # 标定结果保存路径
        self.fps = fps                          # 帧率
        self.laneWidth = laneWidth              # 车道宽度
        self.emgcWidth = emgcWidth              # 应急车道宽度
        self.cellLen = cellLen                  # 元胞长度
        self.qMerge = qMerge                    # 判定元胞为合流区域的流量
        self.count = 0                          # 计数
        # 暂存传感器数据
        self.xyByLane = dict()                  # lane索引的xy
        self.vxyCount = dict()                  # lane索引的vxy的正负计数
        # 车道ID与运动正方向
        self.laneIDs = []
        self.emgcIDs = []
        self.vDirDict = dict()
        # 车道线方程
        self.xyMinMax = dict()                  # lane索引的xy的最大最小值
        self.globalXYMinMax = []    # 全局xy最大最小值[xmin,max, ymin,max]
        self.polyPts = dict()                     # lane索引的四分位特征点
        self.coef = dict()                        # lane索引的曲线方程系数
        # 元胞
        self.cells = dict()                       # lane索引的元胞有效无效列表

    def run(self, msg):
        '''class function receive

        input
        ----------
        msg: list
            list, 代码内流通的数据格式。msg元素为代表一个车辆目标的dict。

        接受每帧传输来的目标信息, 更新给calibrator
        '''
        self.count += 1
        for target in msg:
            laneID = target['laneID'] - 100 if target['laneID'] > 100 \
                else target['laneID']

            # 分配dict索引()
            if laneID not in self.xyByLane:
                self.xyByLane[laneID] = []
                self.vxyCount[laneID] = {'x': 0, 'y': 0}
            # 存储vxy
            self.xyByLane[laneID].append([target['x'], target['y']])
            # 更新vxyCount
            if target['vx'] > 0:
                self.vxyCount[laneID]['x'] += 1
            elif target['vx'] < 0:
                self.vxyCount[laneID]['x'] -= 1
            if target['vy'] > 0:
                self.vxyCount[laneID]['y'] += 1
            elif target['vy'] < 0:
                self.vxyCount[laneID]['y'] -= 1

    def calibrate(self):
        '''class function calibrate

        根据calibrator的属性计算标定结果。
        '''
        # 确定车道ID
        self._distinguishNormalAndEmgcLanes()
        # 标定内外侧车道线ID
        self._distinguishInnerAndOutboardLaneID()
        # 确定运动正方向
        self._distinguishLaneDirection()
        # 计算各lane的xy最大最小值
        self._calibXYMinMax()
        # 计算各lane轨迹四分位特征点
        self._getLaneQuartilesPoints()
        # 计算车道线方程
        self._calculateLanesFunction()
        # 划分元胞
        self._calibCells()

    def _distinguishNormalAndEmgcLanes(self):
        '''class function _distinguishNormalAndEmgcLanes

        return
        ----------
        laneIDs: list
            返回车道ID号, list格式
        emgcIDs: list
            返回应急车道号, list格式

        返回车道ID号, list格式。返回应急车道号, list格式。
        根据self.xyByLane统计车道ID号, 存为list。
        考虑到应急车道, 常规情况下交通量可能为0, 没有对应记录:
        若车道ID号不包含1号车道, 则将1号车道加入。
        上述操作完成后, 将车道ID设为从1到记录的max。
        若最大车道号为奇数, 则补充车道号加1。
        应急车道为1号车道和最大号车道。
        '''
        laneIDs = list(self.xyByLane.keys())
        m = max(laneIDs)
        if m % 2 == 1:    # 若最大车道号为奇数, 则补充车道号加1
            m += 1
        self.laneIDs = list(range(1, m+1))
        self.emgcIDs = [1, m]

    def _distinguishInnerAndOutboardLaneID(self):
        '''class function _distinguishInnerAndOutboardLaneID

        return
        ----------
        intID: int
            返回内侧车道ID号
        extID: int
            返回外侧车道ID号

        计算除应急车道的2个边界车道的轨迹点的分散程度,
        从而确定内侧车道ID号与外侧车道ID号。
        一般来说, 内侧车道距离较短, 车辆轨迹点范围分布较集中,
        外侧车道距离较长, 车辆轨迹点范围分布较分散。
        '''
        # 考量紧急车道内侧的2个车道, 点分散程度大的的车道为外侧车道
        lane2, laneN_1 = self.emgcIDs[0] + 1, self.emgcIDs[1] - 1
        dbi2, dbiN_1 = dbi(self.xyByLane[lane2]), dbi(self.xyByLane[laneN_1])
        if dbi2 < dbiN_1:
            self.intID, self.extID = lane2, laneN_1
        else:
            self.intID, self.extID = laneN_1, lane2

    def _distinguishLaneDirection(self):
        '''class function _distinguishLaneDirection

        return
        ----------
        返回运动正方向, dict格式, {'x': 1, 'y': 1}。
        '''
        self.vDirDict = dict()
        # 确定非应急车道速度正方向
        for id in self.laneIDs:
            if id in self.emgcIDs:
                continue    # 跳过应急车道, 轨迹点数量少不具有代表性
            dir = {'x': 1, 'y': 1}
            if self.vxyCount[id]['x'] < 0:
                dir['x'] = -1
            if self.vxyCount[id]['y'] < 0:
                dir['y'] = -1
            self.vDirDict[id] = dir
        # 确定应急车道速度正方向
        for id in self.emgcIDs:
            if id == 1:
                # copy 2号车道的方向
                tmp = self.vDirDict[id+1].copy()  # 为保存文件不出现乱码, 使用copy
                self.vDirDict[id] = tmp  # 1号车道与2号车道同向
            else:
                tmp = self.vDirDict[id-1].copy()  # 为保存文件不出现乱码, 使用copy
                self.vDirDict[id] = tmp  # 最大车道与倒数第二车道同向

    def _calibXYMinMax(self):
        '''class function _calibXYMinMax

        对各lane的xyByLane分别以x或y排序, 得到最大最小值, 存储到self.xyMinMax。
        self.xyMinMax索引为laneID, 值为[xmin, xmax, ymin, ymax]。
        并对所有lane得到的xyMinMax再次排序, 得到最大最小值, 存储到self.globalXYMinMax。
        self.globalXYMinMax值为[xmin, xmax, ymin, ymax]。
        '''
        self.xyMinMax = dict()
        self.globalXYMinMax = [0, 0, 0, 0]
        # 对各lane的xyByLane分别以x或y排序, 得到最大最小值, 存储到self.xyMinMax
        for lane in self.xyByLane:
            # 以x排序
            self.xyByLane[lane].sort(key=lambda x: x[0])
            xmin, xmax = self.xyByLane[lane][0][0], self.xyByLane[lane][-1][0]
            # 以y排序
            self.xyByLane[lane].sort(key=lambda x: x[1])
            ymin, ymax = self.xyByLane[lane][0][1], self.xyByLane[lane][-1][1]
            # 存储
            self.xyMinMax[lane] = [xmin, xmax, ymin, ymax]
            self.globalXYMinMax[0] = min(self.globalXYMinMax[0], xmin)
            self.globalXYMinMax[1] = max(self.globalXYMinMax[1], xmax)
            self.globalXYMinMax[2] = min(self.globalXYMinMax[2], ymin)
            self.globalXYMinMax[3] = max(self.globalXYMinMax[3], ymax)

    def _getLaneQuartilesPoints(self) -> dict:
        '''class function _getLaneQuartilesPoints

        return
        ----------
        polyPts: dict
            返回车道特征点, dict格式, {laneID: [list]}。
            元素为一个lane轨迹点的四分位特征点, shape=(5, 2)。
        '''
        self.polyPts = dict()
        for id in self.laneIDs:
            if id in self.emgcIDs:
                continue
            featPoints = calQuartiles(self.xyByLane[id])
            self.polyPts.update({id: featPoints})

    def _calculateLanesFunction(self):
        '''class function _calculateLanesFunction

        return
        ----------

        利用存储的轨迹点信息, 计算车道特征点, 拟合出车道方程
        '''
        # 拟合laneExt车道线方程
        self.coef = dict()
        # 实验验证: 采用四分位特征点拟合效果优于直接用轨迹点拟合
        extCoef = poly2fit(np.array(self.polyPts[self.extID]))
        # extCoef = poly2fit(np.array(self.xyByLane[self.extID]))
        self.coef[self.extID] = extCoef

        # 拟合其他非应急车道的车道线方程
        for id in self.laneIDs:
            if (id in self.emgcIDs) | (id == self.extID):
                continue
            # 以extCoef为初始值拟合
            # 实验验证: 采用四分位特征点拟合效果优于直接用轨迹点拟合
            a = poly2fitFrozen(np.array(self.polyPts[id]), extCoef[0])
            # a = poly2fitFrozen(np.array(self.xyByLane[id]), extCoef[0])
            self.coef[id] = a

        # 拟合应急车道的车道线方程
        intCoef = self.coef[self.intID]
        d = (self.laneWidth + self.emgcWidth) / 2   # 边界车道-应急车道距离
        # 计算ext车道线方程系数的导数
        diffCoef = np.polyder(np.poly1d(extCoef))
        # 计算在x=0处的导数值（切线的k值）
        k = np.polyval(diffCoef, 0)
        # 计算边界车道-应急车道距离在y轴上的投影距离
        dY = d * np.sqrt(1 + k**2)
        # 计算应急车道的车道线方程系数
        if self.coef[self.extID][2] > self.coef[self.intID][2]:
            aExtEmgc = [extCoef[0], extCoef[1], extCoef[2] + dY]
            aIntEmgc = [intCoef[0], intCoef[1], intCoef[2] - dY]
        else:
            aExtEmgc = [extCoef[0], extCoef[1], extCoef[2] - dY]
            aIntEmgc = [intCoef[0], intCoef[1], intCoef[2] + dY]
        # 存储应急车道的车道线方程系数
        if self.intID == self.emgcIDs[0] + 1:
            self.coef[self.emgcIDs[0]] = np.array(aIntEmgc)
            self.coef[self.emgcIDs[1]] = np.array(aExtEmgc)
        else:
            self.coef[self.emgcIDs[0]] = np.array(aExtEmgc)
            self.coef[self.emgcIDs[1]] = np.array(aIntEmgc)

    def _calibCells(self):
        '''class function _calibCells

        return
        ----------
        cells: dict
            返回元胞有效无效列表, dict格式, {laneID: [list]}。
            元素为一个lane的元胞有效无效列表,如[True, True, False]。
            对于双向道路, 标定出的cells有效否的顺序, 为沿着车道向前行驶的正方向。
        '''
        # 按全局y最大最小值与元胞长度划分元胞
        ymin, ymax = self.globalXYMinMax[2], self.globalXYMinMax[3]
        pts = cutPts(ymin, ymax, self.cellLen)   # 元胞划分点包括起点终点
        cellNum = len(pts) - 1                   # 元胞数量

        # 各lane将xy点分配到元胞顺序计数
        cellCount = dict()
        for id in self.laneIDs:
            count = [0] * cellNum
            self.xyByLane.setdefault(id, [])
            for xy in self.xyByLane[id]:
                if len(xy):
                    # 根据y大于等于划分点的数量, 确定元胞编号
                    order = np.sum(xy[1] >= pts) - 1
                    count[order] += 1
            cellCount[id] = count

        for id in self.laneIDs:
            if id in self.emgcIDs:
                continue
            # 判定有效性
            # 法1: 计算各元胞在一小时内的经过车辆数
            # valid = []
            # for i in range(cellNum):
            #     q = cellCount[id][i] / (self.count / self.fps) * 3600
            #     valid.append(True if q > self.qMerge else False)
            # 法2: 计算各元胞经过车辆数占该车道总车辆数的比例
            # 比例小于 1 / cellNum / 5 判定为不可用
            valid = [True if x / sum(cellCount[id]) > 1 / cellNum / 5
                     else False for x in cellCount[id]]
            # 对于y运动方向为负的车道, 元胞列表反向(默认从ymin到ymax划分为正向)
            if self.vDirDict[id]['y'] < 0:
                valid.reverse()
            self.cells[id] = valid
        # 将应急车道的cell全部设为False
        for id in self.emgcIDs:
            self.cells[id] = [False] * cellNum
        # TODO若某元胞不可用, 需对其做检查
        # 若该元胞为lane上的第一个或最后一个元胞, 则其确认不可用
        # 若该元胞为lane上的中间元胞, 则检查其前后元胞是否不可用
        # 需保证不可用元胞能够与边缘的不可用元胞相邻，以确保不可用元胞的连续性

    def save(self):
        '''class function save

        将标定结果保存到self.clbPath。
        '''
        clb = dict()
        ymin, ymax = self.globalXYMinMax[2], self.globalXYMinMax[3]
        clb = dict()
        for id in self.laneIDs:
            # 确定起点终点
            start, end = ymin, ymax
            if self.vDirDict[id]['y'] < 0:
                start, end = ymax, ymin
            # 生成实例
            laneClb = {'emgc': False if id not in self.emgcIDs else True,
                       'vDir': self.vDirDict[id],
                       'start': start,
                       'len': abs(start - end),
                       'end': end,
                       'coef': [round(x*1000)/1000 for x in self.coef[id]],
                       'cells': self.cells[id]
                       }
            clb.update({id: laneClb})

        with open(self.clbPath, 'w') as f:
            yaml.dump(clb, f)

        return clb


if __name__ == '__main__':
    # 未更新
    # 生成标定器
    clbPath = './calibration/clb.yml'
    calibrator = Calibrator(clbPath, 20)
    calibrator.emgcIDs = [1, 8]
    calibrator.laneIDs = [1, 2, 3, 4, 5, 6, 7, 8]

    # 标定器标定
    calibrator.calibrate()

    # 标定器保存, 测试保存成功
    calibrator.save()
