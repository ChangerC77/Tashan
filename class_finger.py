import sys
import os

# 获取当前文件所在的目录，并将其父目录加入 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
# parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)

from class_sensorcmd import ClassSensorCmd
from sensorPara import finger_params
from sensorPara import DynamicYddsComTs
from sensorPara import DynamicYddsU16Ts
import time
from ctypes import sizeof
import copy
from finger_log_setting import logging
logger = logging.getLogger(__name__)

# 电容数据存储结构
class capData:
    def __init__(self):
        self.sensorIndex = 0            # 电容序号，与iic addr相同
        self.channelCapData = list()    # 原始通道数值
        self.tf = list()                # 切向力数组
        self.tfDir = list()             # 切向力方向数组
        self.nf = list()                # 法向力数组
        self.sProxCapData = list()      # 接近(自电容)数组
        self.mProxCapData = list()      # 接近（互电容）数组
        self.cnt = 0                                    # 计数，测试用

    def init(self, addr, yddsNum, sProxNum, mProxNum, capChannelNum):
        self.sensorIndex = addr                             # 电容序号，与iic addr相同
        self.channelCapData = list(range(capChannelNum))    # 原始通道数值
        self.tf = list(range(yddsNum))                      # 切向力数组
        self.tfDir = list(range(yddsNum))                   # 切向力方向数组
        self.nf = list(range(yddsNum))                      # 法向力数组
        self.sProxCapData = list(range(sProxNum))           # 接近(自电容)数组
        self.mProxCapData = list(range(mProxNum))           # 接近（互电容）数组
        self.cnt = 0                                        # 计数，测试用

    def deinit(self):
        self.channelCapData = None
        self.tf = None
        self.tfDir = None
        self.nf = None
        self.sProxCapData = None
        self.mProxCapData = None


# 传感器类：包换传感器相关参数
class ClassFinger:
    def __init__(self, pca_idx, ch341):
        self.snsCmd = ClassSensorCmd(ch341)
        self.pcaIdx = pca_idx   # iic使能芯片序号，从2开始
        self.readData = capData()
        self.disconnected()

    # 检查传感器是否连接，如果读写地址正确则认为连接正常
    def checkSensor(self):
        # 广播的方式读取当前传感器地址，并默认将iic地址配置为和pca相同的地址
        addrRead = self.snsCmd.getAddr(0)
        if addrRead != self.pcaIdx:
            if self.pcaIdx != self.snsCmd.setAddr(addrRead, self.pcaIdx):
                logger.error(f"set addr false, setaddr={self.pcaIdx}")
                return False
            else:
                addrRead = self.pcaIdx
                logger.info(f"update iic addr, new addr ={addrRead}")

        # 设置发送数据类型为原始值
        if self.snsCmd.setSensorSendType(addrRead, 0) is not True:
            logger.error(f"setSensorSendType err, addr = {addrRead}")

        # 设置电容采集序列，这里按照地址来分配采集时序，只要每个传感器不同即可
        if self.snsCmd.setSensorCapOffset(addrRead, addrRead) is not True:
            logger.error(f"setSensorCapOffset err, addr = {addrRead}")

        # 实际用户使用中只需要根据使用的传感器来定义参数即可，不需要读取项目号
        projectRead = self.snsCmd.getSensorProjectIdex(addrRead)
        logger.info(f"project={projectRead}")
        findProjectFlg = False
        if projectRead > 0:
            for pro in finger_params:
                if pro.prg == projectRead:
                    self.projectPara = copy.deepcopy(pro)
                    logger.info(f"finger connected, project = {self.projectPara.name}")
                    findProjectFlg = True
                    break

        if findProjectFlg is False:
            logger.error("not found vailed project, project para use default")

        self.connected(addrRead)

        return True

    # 传感器连接，初始化参数
    def connected(self, addr):
        self.addr = addr
        self.connect = True
        self.connectTimer = time.time()
        self.packIdx = 0
        self.data = list()
        self.data.extend(range(self.projectPara.pack_len))

        self.readData.init(addr,
                           self.projectPara.ydds_num,
                           self.projectPara.s_prox_num,
                           self.projectPara.m_prox_num,
                           self.projectPara.sensor_num)

        # logger.info(f"datalen={len(self.data)}")

    # 传感器断开,复位参数
    def disconnected(self):
        self.addr = 0xFF   # iic地址
        self.connect = False   # 连接标志位
        self.packIdx = 0     # 采样序号
        self.connectTimer = 0   # 连接超时计时

        self.projectPara = finger_params[0]

        self.readData.deinit()

    def capRead(self):
        rcvCapDataFlg = False

        for retry in range(0, 3):
            if self.snsCmd.getSensorCapData(self.addr, self.data) is True:
                if self.data[5] != self.projectPara.sensor_num:
                    logger.error(f"cap channel num err, read num = {self.data[5]},\
                    expect num = {self.projectPara.sensor_num}")

                if self.data[4] != self.packIdx:
                    self.packIdx = self.data[4]
                    self.connectTimer = time.time()

                    # 根据通道值占用字节大小获取通道数据
                    if self.projectPara.cap_byte == 4:
                        for j in range(0, self.projectPara.sensor_num):
                            self.readData.channelCapData[j] = ((self.data[6 + j * self.projectPara.cap_byte] & 0xFF) +
                                                               ((self.data[6 + j * self.projectPara.cap_byte + 1] & 0xFF) << 8) +
                                                               ((self.data[6 + j * self.projectPara.cap_byte + 2] & 0xFF) << 16) +
                                                               ((self.data[6 + j * 4 + 3] & 0xFF) << 24))
                    else:
                        for j in range(0, self.projectPara.sensor_num):
                            self.readData.channelCapData[j] = ((self.data[6 + j * self.projectPara.cap_byte] & 0xFF) +
                                                               ((self.data[6 + j * self.projectPara.cap_byte + 1] & 0xFF) << 8) +
                                                               ((self.data[6 + j * self.projectPara.cap_byte + 2] & 0xFF) << 16))

                    yddsOffset = 6 + self.projectPara.sensor_num*self.projectPara.cap_byte

                    if self.projectPara.ydds_type == 2:
                        struct_size = sizeof(DynamicYddsComTs)
                        for i in range(self.projectPara.ydds_num):
                            offset = yddsOffset + i * struct_size
                            struct_data = self.data[offset: offset + struct_size]
                            struct_data = [
                                value & 0xFF for value in struct_data]
                            struct_data = bytes(struct_data)  # 转换为 bytes 类型
                            instance = DynamicYddsComTs.from_buffer_copy(
                                struct_data)
                            self.readData.nf[i] = instance.nf
                            self.readData.tf[i] = instance.tf
                            self.readData.tfDir[i] = instance.tfDir
                            self.readData.sProxCapData[i] = instance.prox
                    elif self.projectPara.ydds_type == 4:
                        struct_size = sizeof(DynamicYddsU16Ts)
                        for i in range(self.projectPara.ydds_num):
                            offset = yddsOffset + i * struct_size
                            struct_data = self.data[offset: offset + struct_size]
                            # logger.info(f"struct={struct_data}")
                            struct_data = [
                                value & 0xFF for value in struct_data]
                            struct_data = bytes(struct_data)  # 转换为 bytes 类型
                            instance = DynamicYddsU16Ts.from_buffer_copy(
                                struct_data)
                            self.readData.nf[i] = instance.nf/100.0
                            self.readData.tf[i] = instance.tf/100.0
                            self.readData.tfDir[i] = instance.tfDir
                        sProxOffset = yddsOffset + self.projectPara.ydds_num*struct_size
                        for i in range(self.projectPara.s_prox_num):
                            self.readData.sProxCapData[i] = ((self.data[sProxOffset + i*self.projectPara.cap_byte] & 0xFF) +
                                                             ((self.data[sProxOffset + i*self.projectPara.cap_byte + 1] & 0xFF) << 8) +
                                                             ((self.data[sProxOffset + i*self.projectPara.cap_byte + 2] & 0xFF) << 16))
                        mProxOffset = yddsOffset + self.projectPara.ydds_num*struct_size
                        for i in range(self.projectPara.m_prox_num):
                            self.readData.mProxCapData[i] = ((self.data[mProxOffset + i*self.projectPara.cap_byte] & 0xFF) +
                                                             ((self.data[mProxOffset + i*self.projectPara.cap_byte + 1] & 0xFF) << 8) +
                                                             ((self.data[mProxOffset + i*self.projectPara.cap_byte + 2] & 0xFF) << 16))

                    rcvCapDataFlg = True

                break
            # else:
            #     logger.error("read err")

        # 2S未接收到数据超时
        if (time.time() - self.connectTimer) > 2:
            self.disconnected()
        
        return rcvCapDataFlg
