import time
import os
import sys
from ctypes import c_byte
from ctypes import c_long
import ctypes
import glob
from finger_log_setting import logging
logger = logging.getLogger(__name__)

if os.name == 'nt':  # Windows 环境
    from ctypes import windll  # 确保导入 windll
elif os.name == 'posix':  # Linux 或 macOS 环境
    from ctypes import cdll  # 确保导入 cdll

import sys
import os

# 获取当前文件所在的目录，并将其父目录加入 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
# parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)

# ch341类：iic读写，int引脚读写，速度设置
class ClassCh341:
    # 接口固定宏
    _mCH341A_CMD_I2C_STREAM = 0xAA      # I2C接口的命令包,从次字节开始为I2C命令流
    _mCH341A_CMD_I2C_STM_STA = 0x74	    # I2C接口的命令流:产生起始位
    _mCH341A_CMD_I2C_STM_STO = 0x75		# I2C接口的命令流:产生停止位
    _mCH341A_CMD_I2C_STM_OUT = 0x80		# I2C接口的命令流:输出数据,位5-位0为长度,后续字节为数据,0长度则只发送一个字节并返回应答
    _mCH341A_CMD_I2C_STM_IN = 0xC0		# I2C接口的命令流:输入数据,位5-位0为长度,0长度则只接收一个字节并发送无应答
    _mCH341A_CMD_I2C_STM_MAX = 63       # I2C接口的命令流单个命令输入输出数据的最大长度
    # I2C接口的命令流:设置参数,位2=SPI的I/O数(0=单入单出,1=双入双出),位1位0=I2C速度(00=低速,01=标准,10=快速,11=高速)
    _mCH341A_CMD_I2C_STM_SET = 0x60
    _mCH341A_CMD_I2C_STM_US = 0x40		# I2C接口的命令流:以微秒为单位延时,位3-位0为延时值
    _mCH341A_CMD_I2C_STM_MS = 0x50		# I2C接口的命令流:以亳秒为单位延时,位3-位0为延时值
    _mCH341A_CMD_I2C_STM_DLY = 0x0F		# I2C接口的命令流单个命令延时的最大值
    _mCH341A_CMD_I2C_STM_END = 0x00		# I2C接口的命令流:命令包提前结束

    _mStateBitINT = 0x00000400

    IIC_SPEED_20 = 0
    IIC_SPEED_100 = 1
    IIC_SPEED_400 = 2
    IIC_SPEED_750 = 3

    def __init__(self):
        self.deviceID = ctypes.c_uint32()
        pass

    def init(self):
        if os.name == 'nt':  # Windows 环境
            libPath = os.path.dirname(
                sys.argv[0]) + r'/lib/ch341/windows/CH341DLLA64.DLL'
        elif os.name == 'posix':

            if hasattr(sys, '_MEIPASS'):
                # 如果运行在 PyInstaller 打包环境中
                # _MEIPASS 指向打包目录的根 (onedir) 或临时解压目录 (onefile)
                # 假设 libch347.so 在打包目录的 _internal 文件夹下
                bundle_root = sys._MEIPASS
                libPath = os.path.join(bundle_root, 'libch347.so')
                logger.info(f"运行在打包环境中。尝试从 _MEIPASS 加载库: {libPath}")
            else:
                # 如果运行在标准的 Python 开发环境中
                # 获取当前脚本文件 (start_project.py) 所在的目录
                script_dir = os.path.dirname(os.path.abspath(__file__))
 
                libPath = os.path.join(script_dir, 'lib', 'ch341', 'CH341PAR_LINUX', 'lib', 'x64', 'dynamic', 'libch347.so') 

                logger.info(f"运行在开发环境中。尝试从脚本目录相对路径加载库: {libPath}")
            # --- 路径构建结束 ---

        dllExist = os.path.exists(libPath)
        if not dllExist:
            logger.error('未找到库文件')
            return False
        else:
            try:
                if os.name == 'nt':  # Windows 环境
                    self.ic = windll.LoadLibrary(libPath)  # ch341接口

                    self.ch341GetInput = self.ic.CH341GetInput
                    self.ch341CloseDevice = self.ic.CH341CloseDevice
                    self.ch341WriteData = self.ic.CH341WriteData
                    self.ch341WriteRead = self.ic.CH341WriteRead
                    self.ch341SetOutput = self.ic.CH341SetOutput
                    self.ch341SetStream = self.ic.CH341SetStream

                elif os.name == 'posix':
                    self.ic = cdll.LoadLibrary(libPath)  # ch341接口

                    self.ch341GetInput = self.ic.CH34xGetInput
                    self.ch341CloseDevice = self.ic.CH34xCloseDevice
                    self.ch341WriteData = self.ic.CH34xWriteData
                    self.ch341WriteRead = self.ic.CH34xWriteRead
                    self.ch341SetOutput = self.ic.CH34xSetOutput
                    self.ch341SetStream = self.ic.CH34xSetStream

                logger.info("ch341加载成功")
                return True
            except Exception as e:
                logger.error(f"ch341加载失败, err = {e}")
                return False

    # 判断ch341是否插入
    # return：0未插入，1插入
    def open(self):
        if os.name == 'nt':  # Windows 环境
            try:
                self.fd = self.ic.CH341OpenDevice(0)
                if self.fd == -1:
                    logger.error("CH341 device open failed on Windows.")
                    return False
                else:
                    self.fd = 0     # todo 改成扫描端口
                    logger.info("CH341 device opened successfully on Windows.")
                    return True
            except Exception as e:
                logger.error(
                    f"Error occurred while opening CH341 device on Windows: {e}")
                return False

        elif os.name == 'posix':  # Linux 环境
            try:
                devices = glob.glob('/dev/ch34x_pis*')  # 动态查找设备
                if devices:
                    device_path = devices[0].encode()
                    self.fd = self.ic.CH34xOpenDevice(device_path)
                    if self.fd == -1:
                        logger.error("CH341 device open failed on Linux.")
                        return False
                    else:
                        logger.info("CH341 device opened successfully on Linux.")
                        return True
                else:
                    logger.error("No CH341 device found on Linux.")
                    return False
            except Exception as e:
                logger.error(
                    f"Error occurred while opening CH341 device on Linux: {e}")
                return False

        else:
            logger.error("Unsupported operating system.")
            return False

    def disconnect(self):
        self.ch341CloseDevice(self.fd)

    def connectCheck(self):
            return self.ch341GetInput(self.fd, ctypes.byref(self.deviceID))

    # iic写数据
    # addr:iic从机地址
    # data：要写的数据列表
    # return：写入长度，不一定正确
    def write(self, addr, data):
        sLen = len(data)
        tmpData = []    # 临时列表
        tmpLen = sLen   # 发送数据

        pack = []   # 发送列表
        cnt = 20    # 每包数量
        packNum = sLen // cnt    # 拆包数量
        sLen %= cnt  # 不足字节数

        tmpData.extend(data)

        pack.append(self._mCH341A_CMD_I2C_STREAM)
        pack.append(self._mCH341A_CMD_I2C_STM_STA)
        pack.append(self._mCH341A_CMD_I2C_STM_OUT | 1)
        pack.append(addr << 1)
        for i in range(0, packNum):
            pack.append(self._mCH341A_CMD_I2C_STM_OUT | cnt)
            pack.extend(tmpData[0:20])
            del tmpData[0:20]
            pack.append(self._mCH341A_CMD_I2C_STM_END)
            sendBuf = (c_byte * len(pack))()
            for j in range(0, len(pack)):
                sendBuf[j] = pack[j]
            sendLen = (c_byte * 1)()
            sendLen[0] = len(pack)
            if not self.ch341WriteData(self.fd, sendBuf, sendLen):
                return 0
            if sendLen == 0:
                return 0
            pack.clear()
            pack.append(self._mCH341A_CMD_I2C_STREAM)
        if sLen >= 1:
            pack.append(self._mCH341A_CMD_I2C_STM_OUT | sLen)
            pack.extend(tmpData[0:sLen])
        pack.append(self._mCH341A_CMD_I2C_STM_STO)
        pack.append(self._mCH341A_CMD_I2C_STM_END)
        sendBuf = (c_byte * len(pack))()
        for j in range(0, len(pack)):
            sendBuf[j] = pack[j]
        sendLen = (c_byte * 1)()
        sendLen[0] = len(pack)
        if not self.ch341WriteData(self.fd, sendBuf, sendLen):
            return 0
        if sendLen == 0:
            return 0
        return tmpLen

    # iic读数据
    # addr：iic从机地址
    # data：读取数据列表。根据列表大小确定读取长度
    # return：读取长度，不一定正确
    def read(self, addr, data):
        if id(data) == 0 or len(data) == 0:
            return 0
        rLen = len(data)
        # logger.info(f"rLen={rLen}")
        pack = []
        readBuf = []
        readLen = 0

        packNum = rLen // 30
        rLen %= 30
        if rLen == 0:
            rLen = 30
            packNum -= 1
        # logger.info(f"packNum={packNum}")
        pack.append(self._mCH341A_CMD_I2C_STREAM)
        pack.append(self._mCH341A_CMD_I2C_STM_STA)
        pack.append(self._mCH341A_CMD_I2C_STM_OUT | 1)
        pack.append((addr << 1) | 0x01)
        pack.append(self._mCH341A_CMD_I2C_STM_MS | 1)
        for i in range(0, packNum):
            pack.append(self._mCH341A_CMD_I2C_STM_IN | 30)
            pack.append(self._mCH341A_CMD_I2C_STM_END)
            sendBuf = (c_byte * len(pack))()
            for j in range(0, len(pack)):
                sendBuf[j] = pack[j]
            recLen = (c_byte * 1)()
            recBuf = (c_byte * self._mCH341A_CMD_I2C_STM_MAX)()
            if not self.ch341WriteRead(self.fd,
                                       len(pack),
                                       sendBuf,
                                       self._mCH341A_CMD_I2C_STM_MAX,
                                       1,
                                       recLen,
                                       recBuf):
                return 0
            if recLen == 0:
                return 0
            for j in range(0, recLen[0]):
                readBuf.append(recBuf[j])
            readLen += 30
            pack.clear()
            pack.append(self._mCH341A_CMD_I2C_STREAM)
        if rLen > 1:
            pack.append(self._mCH341A_CMD_I2C_STM_IN | (rLen - 1))
        pack.append(self._mCH341A_CMD_I2C_STM_IN | 0)
        pack.append(self._mCH341A_CMD_I2C_STM_STO)
        pack.append(self._mCH341A_CMD_I2C_STM_END)
        sendBuf = (c_byte * len(pack))()
        for j in range(0, len(pack)):
            sendBuf[j] = pack[j]
        recLen = (c_byte * 1)()
        recBuf = (c_byte * self._mCH341A_CMD_I2C_STM_MAX)()
        if not self.ch341WriteRead(self.fd,
                                   len(pack),
                                   sendBuf,
                                   self._mCH341A_CMD_I2C_STM_MAX,
                                   1,
                                   recLen,
                                   recBuf):
            return 0
        if recLen[0] == 0:
            return 0
        for j in range(0, recLen[0]):
            readBuf.append(recBuf[j])
        data.clear()
        data.extend(readBuf)
        readLen = len(pack)
        # logger.info(f"readLen={len(readBuf)}")
        return readLen

    # 设置int引脚状态
    # lvl：高低电平。1高电平，0低电平
    def set_int(self, lvl):
        status = (c_long * 1)()
        self.ic.CH341GetInput(0, status)
        time.sleep(0.01)
        if lvl:
            self.ch341SetOutput(self.fd,
                                0x03,
                                0xFF00,
                                status[0] | self._mStateBitINT)
        else:
            self.ch341SetOutput(self.fd,
                                0x03,
                                0xFF00,
                                status[0] & (~self._mStateBitINT))

    # 读取int引脚状态
    # 返回：高低电平
    def get_int(self):
        status = (c_long * 1)()
        self.ic.CH341GetInput(0, status)
        return (status[0] & self._mStateBitINT) >> 10

    # 设置IIC速度
    # return：0错误，1成功
    def set_speed(self, speed):
        if speed != self.IIC_SPEED_20 \
                and speed != self.IIC_SPEED_100 \
                and speed != self.IIC_SPEED_400 \
                and speed != self.IIC_SPEED_750:
            return False
        if self.ch341SetStream(self.fd, speed | 0) is False:
            logger.error("speed err")
            return False
        else:
            return True
