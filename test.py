from cap_read import getFingerData
from cap_read import threadFingerRead
from cap_read import fingerExit
import threading
import time  # 导入 queue 模块
from finger_log_setting import logging
logger = logging.getLogger(__name__)

global exitFlg
exitFlg = False

def fingerReadHandle(arg1, arg2):
    while exitFlg is False:
        fingerData = getFingerData(True)
        if fingerData is not None:
            logger.info(f"index={fingerData.sensorIndex}")
            logger.info(f"capChannelDat={fingerData.channelCapData}")
            for i in range(len(fingerData.nf)):
                logger.info(f"nf[{i}] = {fingerData.nf[i]}")
                logger.info(f"tf[{i}] = {fingerData.tf[i]}")
                logger.info(f"tfDir[{i}] = {fingerData.tfDir[i]}")
            logger.info(f"sProxCapData = {fingerData.sProxCapData}")
            logger.info(f"mProxCapData = {fingerData.mProxCapData}")

        
# 创建线程对象
threadCapRead = threading.Thread(target=fingerReadHandle, args=("arg1_value", "arg2_value"))

def main():
    threadCapRead.start()
    threadFingerRead.start()
    # time.sleep(2)
    # global exitFlg
    # exitFlg = True
    # threadCapRead.join()
    # fingerExit()
    
if __name__ == "__main__":
    main()