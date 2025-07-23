import sys
import os

# 获取当前文件所在的目录，并将其父目录加入 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
# parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)

from enum import Enum
import threading
import queue  # 导入 queue 模块
from class_ch341 import ClassCh341
from class_finger import ClassFinger
from sensorPara import FingerParamTS
from finger_log_setting import finger_setup_logging
import socket
import time
from dataclasses import dataclass, field
from typing import List
from finger_log_setting import logging
logger = logging.getLogger(__name__)

DEF_CDC_SYNC_MS = 1000  # 电容同步间隔
DEF_GET_CAP_MS = (15)   # 读取电容间隔
DEF_PRO_CYC = 100

DEF_MAX_FINGER_NUM = 1  # 需要连接的手指数量，最大5个

DEF_USE_VOFA_DEBUG = 0 # 是否要使用vofa调试

@dataclass
class fingerDataPack:
    sensorIndex: int
    channelCapData: List[int]
    nf: List[float]
    tf: List[float]
    tfDir: List[int]
    sProxCapData: List[int]
    mProxCapData: List[int]
    config: FingerParamTS = field(default=None, repr=False)  # 允许传递配置，但不打印

    # def __post_init__(self):
    #     if self.config:
    #         """ 通过全局配置检查 list 长度 """
    #         if len(self.tfDir) != self.config.ydds_num:
    #             logger.error(f"tfDir 长度错误，期望 {self.config.ydds_num}，实际 {len(self.tfDir)}")
    #         if len(self.tf) != self.config.ydds_num:
    #             logger.error(f"tf 长度错误，期望 {self.config.ydds_num}，实际 {len(self.tf)}")
    #         if len(self.nf) != self.config.ydds_num:
    #             logger.error(f"nf 长度错误，期望 {self.config.ydds_num}，实际 {len(self.nf)}")
    #         if len(self.sProxCapData) != self.config.s_prox_num:
    #             logger.error(f"sProxCapData 长度错误，期望 {self.config.s_prox_num}，实际 {len(self.sProxCapData)}")
    #         if len(self.mProxCapData) != self.config.m_prox_num:
    #             logger.error(f"mProxCapData 长度错误，期望 {self.config.m_prox_num}，实际 {len(self.mProxCapData)}")
    #         if len(self.channelCapData) > self.config.sensor_num:
    #             logger.error(f"channelCapData 长度超限，最大 {self.config.sensor_num}，实际 {len(self.channelCapData)}")

# 定义一个全局的队列，用于线程间通信
fingerDataQueue = queue.Queue()
fingerThreadExitQueue = queue.Queue()


# 341通信
class EnumCh341ConnectStatus(Enum):
    CH341_CONNECT_INIT = 0
    CH341_CONNECT_OPEN = 1
    CH341_CONNECT_SET_SPEED = 2
    CH341_CONNECT_SAMPLE_START = 3
    CH341_CONNECT_CHECK = 4
    CH341_CONNECT_SAMPLE_STOP = 5


class ClassCapRead:
    def __init__(self):
        self.ch341 = ClassCh341()

        # 最大连接5个手指
        self.fingers = list()   # 传感器列表
        for i in range(DEF_MAX_FINGER_NUM):
            self.fingers.append(ClassFinger(2+i, self.ch341))

        self.currCh341State = 0  # 当前ch341连接状态
        self.prevCh341State = 0  # 上次ch341连接状态

        self.ch341CheckTimer = 0
        self.mcuInit = 0
        self.pcaAddr = 0x70    # iic控制芯片地址

        self.ch341Init = 0  # ch341初始化标志位

        self.syncTimer = 0

        self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_INIT

        self.connectDebug()

        finger_setup_logging()

        self.exitFlg = False

    def __del__(self):
        self.disConnectDebug()
        self.ch341.disconnect()
        self.exitFlg = True
        logger.info("ch341释放")
    
    def deInit(self):
        self.disConnectDebug()
        self.ch341.disconnect()
        self.exitFlg = True
        logger.info("ch341释放")


    def connectDebug(self):
        if DEF_USE_VOFA_DEBUG == 1:
            # 连接到调试的服务器
            self.vofaClient = socket.socket()
            addr = ('127.0.0.1', 1347)
            try:
                self.vofaClient.connect(addr)
                # client.send('hello world\r\n'.encode())
                self.socketConnected = True
                logger.info('连接服务器成功')
            except Exception as e:
                self.socketConnected = False
                logger.error(f'连接服务器失败, err = {e}')

    def disConnectDebug(self):
        if DEF_USE_VOFA_DEBUG == 1:
            if self.vofaClient:
                self.vofaClient.close()

    def debugPrint(self):
        if DEF_USE_VOFA_DEBUG == 1:
            if self.socketConnected is True:
                fingerIndex = 0
                _log1 = ""
                # 输出原始通道数值
                # for index in range(0, self.fingers[fingerIndex].projectPara.sensor_num):
                #     _log1 += str(self.fingers[fingerIndex].readData.channelCapData[index])
                #     _log1 += ','
                for index in range(0, self.fingers[fingerIndex].projectPara.ydds_num):
                    _log1 += str(int(self.fingers[fingerIndex].readData.nf[index]*1000))
                    _log1 += ','
                    _log1 += str(int(self.fingers[fingerIndex].readData.tf[index]*1000))
                    _log1 += ','
                    _log1 += str(self.fingers[fingerIndex].readData.tfDir[index])
                    _log1 += ','
                for index in range(0, self.fingers[fingerIndex].projectPara.s_prox_num):
                    _log1 += str(self.fingers[fingerIndex].readData.sProxCapData[index])
                    _log1 += ','
                for index in range(0, self.fingers[fingerIndex].projectPara.m_prox_num):
                    _log1 += str(self.fingers[fingerIndex].readData.mProxCapData[index])
                    _log1 += ','

                _log1 += str(0)
                _log1 += '\r\n'
                # logger.error(_log1)
                if self.socketConnected == 1:
                    self.vofaClient.send(_log1.encode())

    def set_sensor_enable(self, idx):
        _pack = list()
        _pack.append(idx)
        self.ch341.write(self.pcaAddr, _pack)

    def ch341Connect(self):
        if self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_INIT:
            if self.ch341.init() is True:
                self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_OPEN
        elif self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_OPEN:
            if self.ch341.open() is True:
                self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_SET_SPEED
            else:
                self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_INIT
        elif self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_SET_SPEED:
            if self.ch341.set_speed(self.ch341.IIC_SPEED_400) is True:
                self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_SAMPLE_START
            else:
                logger.error("set speed err")
                self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_SAMPLE_START

        elif self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_SAMPLE_START:
            self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_CHECK
            self.timer = threading.Timer(DEF_GET_CAP_MS/1000, self.capRead)
            self.timer.start()
        elif self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_CHECK:
            self.ch341CheckTimer += DEF_PRO_CYC
            if self.ch341CheckTimer >= 1000:
                self.ch341CheckTimer = 0
                if self.ch341.connectCheck() is False:
                    logger.info("ch341 拔出")
                    self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_SAMPLE_STOP
        elif self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_SAMPLE_STOP:
            self.syncTimer = 0
            for i in range(0, len(self.fingers)):
                self.fingers[i].disconnected()
            self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_INIT
        else:
            self.connectStatus = EnumCh341ConnectStatus.CH341_CONNECT_INIT

    def capRead(self):
        if self.exitFlg is False:
            capReadTime = time.time()
            ms_capReadTime = capReadTime

            connectedSensorChan = 0
            connectedSensorCnt = 0
            for fingerIndex in range(0, len(self.fingers)):
                self.set_sensor_enable(1 << (self.fingers[fingerIndex].pcaIdx))
                connectedSensorChan |= 1 << (self.fingers[fingerIndex].pcaIdx)

                if self.fingers[fingerIndex].connect is False:
                    if self.fingers[fingerIndex].checkSensor() is True:
                        logger.info(f"sensor[{fingerIndex}] connected")
                    else:
                        logger.error(f"addr = {fingerIndex}, connected false")
                else:
                    if self.fingers[fingerIndex].capRead() is True:
                                        
                        # 创建一个 fingerDataPack 实例
                        cap_read = fingerDataPack(
                            sensorIndex = fingerIndex,
                            channelCapData = self.fingers[fingerIndex].readData.channelCapData,
                            nf=self.fingers[fingerIndex].readData.nf,
                            tf=self.fingers[fingerIndex].readData.tf,
                            tfDir = self.fingers[fingerIndex].readData.tfDir,
                            sProxCapData = self.fingers[fingerIndex].readData.sProxCapData,
                            mProxCapData = self.fingers[fingerIndex].readData.mProxCapData,
                            # config=self.fingers[fingerIndex].projectPara  # 传递当前配置
                        )

                        fingerDataQueue.put(cap_read)
                    connectedSensorCnt += 1

            self.debugPrint()

            # 大于1个传感器连接需要设置接近采集序列
            if connectedSensorCnt > 1 and (time.time() - self.syncTimer) > DEF_CDC_SYNC_MS:
                self.syncTimer = time.time()
                self.set_sensor_enable(connectedSensorChan)
                for fingerIndex in range(0, len(self.fingers)):
                    if self.fingers[fingerIndex].connect is True:
                        self.fingers[fingerIndex].snsCmd.setSensorSync(0)
                        break

            if self.connectStatus == EnumCh341ConnectStatus.CH341_CONNECT_CHECK:
                capReadTime = time.time()
                difftime = int(capReadTime*1000-ms_capReadTime*1000)
                # logger.error(f"diffTime={difftime}")
                # 定时器在任务完成后重新启动
                if difftime > DEF_GET_CAP_MS:
                    timer = threading.Timer(DEF_GET_CAP_MS/1000, self.capRead)
                else:
                    timer = threading.Timer(
                        (DEF_GET_CAP_MS-difftime)/1000, self.capRead)
                timer.start()

def getFingerData(noWait):
    if noWait is True:
        try:
            # 尝试从队列中获取一个项目，非阻塞方式
            conMsg = fingerDataQueue.get_nowait()
            return conMsg
        except queue.Empty:
            return None
    else:
        fingerData = fingerDataQueue.get()
        fingerDataQueue.task_done()

        return fingerData

def fingerExit():
    conMsg = True
    fingerThreadExitQueue.put(conMsg)

def fingerReadThread(arg1, arg2):
    # 线程的主体功能
    cap = ClassCapRead()

    while cap.exitFlg is False:
        cap.ch341Connect()
        time.sleep(DEF_PRO_CYC/1000)
        
        try:
            # 尝试从队列中获取一个项目，非阻塞方式
            conMsg = fingerThreadExitQueue.get_nowait()
            if conMsg is True:
                cap.exitFlg = True
        except queue.Empty:
            pass

        if cap.exitFlg is True:
            break
    cap.deInit()

# 创建线程对象
threadFingerRead = threading.Thread(target=fingerReadThread, args=("arg1_value", "arg2_value"))