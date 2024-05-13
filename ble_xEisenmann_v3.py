# coding=utf-8

from threading import Thread
from datetime import datetime
import bluepy3.btle as btle

from periphery import GPIO
import os
import glob
import time
import struct
import serial

import ble_agent_v1 as ble_agent
import ble_xEisenmann_utility_v1 as utility


def checkSim7070g():
    ser = serial.Serial("/dev/ttyS2", 115200)
    ser.flushInput()

    ser.write('AT\r\n'.encode())
    time.sleep(1)
    ser.write('AT\r\n'.encode())
    time.sleep(1)
    ser.write('AT\r\n'.encode())
    time.sleep(1)

    if ser.inWaiting():
        time.sleep(0.01)
        recBuff = ser.read(ser.inWaiting())
        print("try to start PPP\r\n" + recBuff.decode())
        if 'OK' in recBuff.decode():
            print("SIM7070G is ready\r\n")
            return True

    return False


def powerToggle(powerKey):
    power_pin = 75
    power_gpio = GPIO(power_pin, "out")
    power_gpio.write(True)
    print("pin 75 -> HIGH")
    time.sleep(2.0)
    power_gpio.write(False)
    print("pin 75 -> LOW")
    power_gpio.close()


def otaConnection(mac_address, ota_path, interface):
    global device_ota_saved
    try:        
        updateFile = open(ota_path, "rb")
        data = updateFile.read()
        time.sleep(2)
        
        print("agent ota connecting...")
        device = btle.Peripheral(mac_address, iface=interface)
        print("agent connected!")
        device.setMTU(250)
    
        services = device.getServices()
        for s in services:
            print("services: %s" % s.uuid.getCommonName())
            c = s.getCharacteristics()
            for ch in c:
                print(ch.getHandle(), ch.uuid.getCommonName(), ch.propertiesToString())

        response  = device.writeCharacteristic(10, b"\x00", True)
        print(response)
        
        dataRead = 0
        while dataRead < len(data):
            if dataRead+244 < len(data):
                d = data[dataRead:dataRead+244]
                dataRead = dataRead + 244
            else:
                d = data[dataRead:len(data)]
                dataRead = len(data)
            print("data sent: %u/%u" % (dataRead, len(data)))
            device.writeCharacteristic(12, d, False)
            time.sleep(0.02)
        
        print("wait")
        time.sleep(5)
        
        busy = True
        while busy:
            print("end request")
            try:
                response  = device.writeCharacteristic(10, b"\x03", True)
                print(response)
                busy = False
            except Exception as e:
                print(e)
                if "Helper not started" in str(e):
                    break
                time.sleep(1)
            
        response  = device.writeCharacteristic(10, b"\x04", True)
        print(response)
    except Exception as e:
        print(e)
    finally:
        print("agent end")
        if mac_address in device_ota_saved:
            device_ota_saved.remove(mac_address)


def connection(mac_address, config, firmware_version, interface):
    global devices_saved
    now = datetime.now()
    now_string = now.strftime("%Y/%m/%d %H:%M:%S") 
    print("%s: agent for %s" % (now_string, mac_address))

#     config = ["2g", "100Hz", "500", "10000"]
#     for i in range(len(config)):
#         print"config: %s" % config[i]
    
    valueCh_password = "0000"
    
    handleCh_OTA 			= 23
    handleCh_notification 	= 27
    handleCh_syncStatus 	= 57
    handleCh_shockStatus 	= 60
    handleCh_dataStatus 	= 63
    handleCh_changeParams 	= 68
    handleCh_closeReq 		= 70
    handleCh_odr			= 77
    handleCh_cntl1			= 79
    handleCh_changeReg		= 89
    handleCh_samples		= 93
    handleCh_syncParameters = 97
    handleCh_shockRequest 	= 101
    handleCh_dataRequest 	= 104
    handleCh_password 		= 108
    handleCh_data_th 		= 111
    handleCh_battery 		= 113
    handleCh_firmware 		= 116
    
    try:
        print("agent connecting...")
        notifyAgent = ble_agent.agentNotify(mac_address, interface)
        print("agent connected!")
        delegate = ble_agent.myDelegateNotify(mac_address)
        notifyAgent.bleDelegate(delegate)
        notifyAgent.bleSetMTU(250)
        response = notifyAgent.bleWriteCh(handleCh_password, valueCh_password, True)
        response = notifyAgent.bleWriteCh(handleCh_notification, b"\x01\x00", True)
        
        for i in range(5):
            time.sleep(1.0)
            response = notifyAgent.bleWriteCh(handleCh_changeParams, b"\x01", True) 
            responseP = ord(notifyAgent.bleReadCh(handleCh_changeParams))
            print("responseP %u" % responseP)
            if responseP != 0:
                break
        
        shock_status = ord(notifyAgent.bleReadCh(handleCh_shockStatus))
#        print"shock status %u" % shock_status
        if shock_status == 1:
            response = notifyAgent.bleWriteCh(handleCh_shockRequest, b"\x01", True)
            shock_status = ord(notifyAgent.bleReadCh(handleCh_shockStatus))
            
        data_status = ord(notifyAgent.bleReadCh(handleCh_dataStatus))
        print("data status %u" % data_status)
        if data_status == 1:
            response = notifyAgent.bleWriteCh(handleCh_dataRequest, b"\x01", True)
            while (not delegate.data_periodic_received):
                notifyAgent.device.waitForNotifications(1.0)
            data_status = ord(notifyAgent.bleReadCh(handleCh_dataStatus))
            
#        printdelegate.error
        if not delegate.error:
            now = datetime.now()
            now_string = now.strftime("%Y%m%d.%H%M%S")  
            if delegate.data_shock_received:
                file_name = "Data/" + mac_address.replace(":", "") + "-" + now_string + "-6.25Hz-2g_shock.bin"
                with open(file_name, 'w') as file_shock:
                    file_shock.write(delegate.data_shock)
                    file_shock.close()
                
            if delegate.data_periodic_received:
                freq = ord(notifyAgent.bleReadCh(handleCh_odr))
                if freq == 0: freq_s = "0.781Hz"
                elif freq == 1: freq_s = "1.563Hz"
                elif freq == 2: freq_s = "3.125Hz"
                elif freq == 3: freq_s = "6.25Hz"
                elif freq == 4: freq_s = "12.5Hz"
                elif freq == 5: freq_s = "25Hz"
                elif freq == 6: freq_s = "50Hz"
                elif freq == 7: freq_s = "100Hz"
                elif freq == 8: freq_s = "200Hz"
                elif freq == 9: freq_s = "400Hz"
                elif freq == 10: freq_s = "800Hz"
                elif freq == 11: freq_s = "1600Hz"
                elif freq == 12: freq_s = "3200Hz"
                elif freq == 13: freq_s = "6400Hz"
                elif freq == 14: freq_s = "12800Hz"
                else: freq_s = "25600Hz"
                scale = ord(notifyAgent.bleReadCh(handleCh_cntl1))
                scale = (scale & 0x18) >> 3
                if scale == 0: scale_s = "2g"
                elif scale == 1: scale_s = "4g"
                elif scale == 2: scale_s = "8g"
                else: scale_s = "16g"
                file_name = "Data/" + mac_address.replace(":", "") + "-" + now_string + "-" + freq_s + "-" + scale_s + "_periodic.bin"
                with open(file_name, 'w') as file_periodic:
                    file_periodic.write(delegate.data_periodic)
                    file_periodic.close()
            else:
                freq = ord(notifyAgent.bleReadCh(handleCh_odr))
                if freq == 0: freq_s = "0.781Hz"
                elif freq == 1: freq_s = "1.563Hz"
                elif freq == 2: freq_s = "3.125Hz"
                elif freq == 3: freq_s = "6.25Hz"
                elif freq == 4: freq_s = "12.5Hz"
                elif freq == 5: freq_s = "25Hz"
                elif freq == 6: freq_s = "50Hz"
                elif freq == 7: freq_s = "100Hz"
                elif freq == 8: freq_s = "200Hz"
                elif freq == 9: freq_s = "400Hz"
                elif freq == 10: freq_s = "800Hz"
                elif freq == 11: freq_s = "1600Hz"
                elif freq == 12: freq_s = "3200Hz"
                elif freq == 13: freq_s = "6400Hz"
                elif freq == 14: freq_s = "12800Hz"
                else: freq_s = "25600Hz"
                scale = ord(notifyAgent.bleReadCh(handleCh_cntl1))
                scale = (scale & 0x18) >> 3
                if scale == 0: scale_s = "2g"
                elif scale == 1: scale_s = "4g"
                elif scale == 2: scale_s = "8g"
                else: scale_s = "16g"
                file_name = "Data/" + mac_address.replace(":", "") + "-" + now_string + "-" + freq_s + "-" + scale_s + "_periodic.bin"
                with open(file_name, 'w') as file_periodic:
                    file_periodic.write("Null")
                    file_periodic.close()
                
        try:
            battery_status = notifyAgent.bleReadCh(handleCh_battery)
            battery_status = ord(battery_status[0]) + (ord(battery_status[1]) << 8)
            print("Battery level: " + str(battery_status))
            if (battery_status < 2950):
                with open("/home/rock/Documents/alarm.txt", 'a') as file_alarm:
                    file_alarm.write("Warning: " + mac_address + " battery voltage too low ->" + str(battery_status) + "\r\n")
                    file_alarm.close()
        except Exception as e:
            print("no battery characteristic")
            
        try:
            actual_firmware_version = str(notifyAgent.bleReadCh(handleCh_firmware).split("_v")[1])
            print("Firmware version: " + actual_firmware_version)
        except Exception as e:
            print("no firmware version characteristic")

        try:
            # se la versione del firmware è diversa da quella presente nel server eisenmann allora iniziare la procedura OTA
            test = int(actual_firmware_version.split("\x00")[0])
            if (test < firmware_version):
                print("start OTA for device: " + mac_address)
                response = notifyAgent.bleWriteCh(handleCh_OTA, b"\x01", True)
        except Exception as e:
            print(e)
            print("no OTA characteristic")
            
        cntl1 = 0xA0
        try:
            if config[0] == "16g": cntl1 |= 0x18 
            elif config[0] == "8g": cntl1 |= 0x10
            elif config[0] == "4g": cntl1 |= 0x08
        except Exception as e:
            cntl1 = 0xA0
        
        odr = 0x07
        try:
            if config[1] == "0.781Hz": odr = 0x00
            elif config[1] == "1.563Hz": odr = 0x01
            elif config[1] == "3.125Hz": odr = 0x02
            elif config[1] == "6.25Hz": odr = 0x03
            elif config[1] == "12.5Hz": odr = 0x04
            elif config[1] == "25Hz": odr = 0x05
            elif config[1] == "50Hz": odr = 0x06
            elif config[1] == "100Hz": odr = 0x07
            elif config[1] == "200Hz": odr = 0x08
            elif config[1] == "400Hz": odr = 0x09
            elif config[1] == "800Hz": odr = 0x0A
            elif config[1] == "1600Hz": odr = 0x0B
            elif config[1] == "3200Hz": odr = 0x0C
            elif config[1] == "6400Hz": odr = 0x0D
            elif config[1] == "12800Hz": odr = 0x0E
            elif config[1] == "25600Hz": odr = 0x0F
        except Exception as e:
            odr = 0x07
        
        try:
            shock = int(config[2]) / 1000.0
            shockTh = int(shock * 256)
            shockMSB = ( shockTh >> 8 ) & 0x07
            shockLSB = shockTh & 0xFF
            if shock >= 8.0:
                shockMSB = 0x07
                shockLSB = 0xFF
        except Exception as e:
            shockMSB = 0x00
            shockLSB = 0x50
            
        try:
            samples = int(config[3])
            samplesMSB = ( samples >> 8 ) & 0xFF
            samplesLSB = samples & 0xFF
            if samples > 65535:
                samplesMSB = 0xFF
                samplesLSB = 0xFF
        except Exception as e:
            samplesMSB = 0x03
            samplesLSB = 0xE8
            
        timing = 3
        try:
            if config[4] == "1h": timing = 1
            elif config[4] == "2h": timing = 2
            elif config[4] == "3h": timing = 3
            elif config[4] == "4h": timing = 4
            elif config[4] == "5h": timing = 5
            elif config[4] == "6h": timing = 6
            elif config[4] == "7h": timing = 7
            elif config[4] == "8h": timing = 8
            elif config[4] == "9h": timing = 9
            elif config[4] == "10h": timing = 10
            elif config[4] == "11h": timing = 11
            elif config[4] == "12h": timing = 12
        except Exception as e:
            timing = 3
            
        try:
            data_th = int(config[5])
            data_thMSB = ( data_th >> 8 ) & 0xFF
            data_thLSB = data_th & 0xFF
            if data_th > 65535:
                data_thMSB = 0xFF
                data_thLSB = 0xFF
            data_th_p = [data_thLSB, data_thMSB]
            notifyAgent.bleWriteCh(handleCh_data_th, struct.pack('B'*len(data_th_p), *data_th_p), True)
            res_th = notifyAgent.bleReadCh(handleCh_data_th)
            res_th = ord(res_th[0]) + (ord(res_th[1]) << 8)
            print("data threshold: " + str(res_th))
        except Exception as e:
            data_thMSB = 0xFF
            data_thLSB = 0xFF
        
        sync_status = ord(notifyAgent.bleReadCh(handleCh_syncStatus))
        print("sync status %u" % sync_status)        
        if sync_status == 1:
            now = datetime.now()
            parameters = [now.year-2000, now.month, now.day, now.hour, now.minute, now.second, cntl1, odr, shockMSB, shockLSB, samplesMSB, samplesLSB, timing]
            response = notifyAgent.bleWriteCh(handleCh_syncParameters, struct.pack('B'*len(parameters), *parameters), True)
        else:
            response = notifyAgent.bleWriteCh(handleCh_closeReq, b"\x01", True)
    except Exception as e:
        print(e)
    finally:
        print("agent end")
        if mac_address in devices_saved:
            devices_saved.remove(mac_address)


def scanning():
    global devices_to_connect
    global devices_saved
    global device_ota_saved
    global device_ota_to_connect
    global scan_active
    scan_active = True
    agent = ble_agent.agentScanner(1)
    
    while True:
        #print"agent scan"
        try:
#             printdevice_ota_saved
#             printdevices_saved
            if devices_saved == [] and device_ota_saved == []:
                devices_to_connect = []
                device_ota_to_connect = []
                agent.bleScan(3.0)
                for dev in agent.scanned_devices:
                    for (adtype, desc, value) in dev.getScanData():
#                         print(adtype, desc, value)
                        if adtype == 9 and value[0:13] == "WisepowerBlue":
                            if dev.addr not in devices_saved:
                                devices_saved.append(dev.addr)
                                devices_to_connect.append(dev.addr)
                        elif adtype == 9 and value == u'OTA':
#                             printdevice_ota_saved
                            if dev.addr not in device_ota_saved:
                                device_ota_saved.append(dev.addr)
                                device_ota_to_connect.append(dev.addr)
            else:
                time.sleep(1.0)
        except Exception as e:
            scan_active = False
            print(e)     
            break
                      
    
    
def main():
    global devices_to_connect
    global devices_saved
    global device_ota_saved
    global device_ota_to_connect
    global scan_active

    gateway_file_version = "GW-IOT001P100-03"

    SERVER_NAME = 'ftp.wisepower.it'
    SERVER_PORT = 22
    SERVER_USER_NAME = '1451303@aruba.it'
    SERVER_PASSWORD = 'QWEasz123'

    scan_active = False
    connection_established = False
    
    interface_index = 0
    count_nError = 0
    new_firmware_version = 0
    old_firmware_version = 0
    interface_index = 0
    
    file_to_send = []
    device_ota_to_connect = []
    device_ota_saved = []
    devices_saved = []
    devices_to_connect = []
    
    map_config = {}
    new_config = {}
    
    local_path_config = "/home/radxa/Documents/config.txt"
    remote_path_config = "www.wisepower.it/ws_iot/config.txt"
    local_path = "/home/radxa/Documents/"
    gbl_path = "/home/radxa/Documents/gbl/"
    data_path = "/home/radxa/Documents/Data/"
    remote_path = "/home/wisepower/files_wisepower/"
    remote_path_gbl = "/home/wisepower/files_wisepower/gbl/"
    alarm_path = "/home/radxa/Documents/alarm.txt"
    default_config = ["2g", "6400Hz", "500", "10000", "1h", "900"]
    os.chdir(local_path)
    
    # try:
    #     os.system("poff rnet")
    # except Exception as e:
    #     print(e)
        
    # time.sleep(1.0)
    
    # try:
    #     os.system("sh /home/rock/Documents/pi_gpio_init.sh")
    # except Exception as e:
    #     print(e)

    # time.sleep(1.0)

    # try:
    #     os.system("pon rnet")
    # except Exception as e:
    #     print(e)
    
    while not connection_established:
        try:
            from ftplib import FTP
            ftp_session = FTP("ftp.wisepower.it", "1451303@aruba.it", "QWEasz123*", timeout=60)
            ftp_session.cwd("www.wisepower.it/ws_iot")

            stored_files = ftp_session.nlst()[2:]
            for f in stored_files:
                if f == "config.txt":
                    with open(f, "w") as fp:
                        ftp_session.retrlines('RETR %s' % f, fp.writelines)
            # client = utility.openSSHConnection(SERVER_NAME, SERVER_PORT, SERVER_USER_NAME, SERVER_PASSWORD)
            # sftp = utility.openFTPSession(client)

            with open(local_path_config, 'r') as f:
                config_list = []
                stop = False
                while not stop:
                    line = f.readline()[:-1]
                    if line == '': stop = True
                    else: config_list.append(line.split(" "))
                    
                    for x in config_list:
                        map_config[x[0]] = x[1:]

            ftp_session.quit()

            # map_config = utility.getConfigFile(sftp, remote_path_config, local_path_config, map_config, new_config)
            # utility.closeFTPSession(sftp)
            # utility.closeSSHConnection(client)


            connection_established = True


        except Exception as e:
            print(e)
            # count_nError = count_nError + 1
            # print("Restart Network")
            # os.system("poff rnet")
            # time.sleep(1.0)
            # powerToggle(75)
            # time.sleep(15.0)
            # check = checkSim7070g()
            # os.system("pon rnet")
            # time.sleep(10.0)


    while True:
        try:
            try:
                with open("config.txt") as f:
                    config_list = []
                    stop = False
                    while not stop:
                        line = f.readline()[:-1]
                        if line == '': stop = True
                        else: config_list.append(line.split(" "))
                
                    for x in config_list:
                        map_config[x[0]] = x[1:]
                    f.close()
            except Exception as e:
                print(e)
                
            if not scan_active:
                # os.system('hciconfig hci0 down && hciconfig hci0 up')
                os.system('hciconfig hci1 down && hciconfig hci1 up')
                time.sleep(1.0)
                singleAgentScanning = Thread(target=scanning)
                singleAgentScanning.daemon = True
                singleAgentScanning.start()
            
            try:
                if devices_saved == [] and device_ota_saved == []:
                    file_to_send = glob.glob(data_path + "*.bin")
                    print(file_to_send)
                    # if file_to_send != []:
                    #     client = utility.openSSHConnection('188.219.249.134', 2022, 'wisepower', 'wisepower!')
                    #     sftp = utility.openFTPSession(client)
                    #     for f in file_to_send:
                    #         utility.saveDataIntoServer(sftp, f, remote_path+(f.split("/")[-1]))
                    #         os.remove(f)
                    #     # utility.saveDataIntoServer(sftp, alarm_path, remote_path+"alarm.txt")
                    #     # utility.updateAlarmFileIntoServer(sftp) # riga giusta
                    #     map_config = utility.getConfigFile(sftp, remote_path_config, local_path_config, map_config, new_config)
                    #     utility.getFirmwareFile(sftp, remote_path_gbl, gbl_path)
                    #     utility.closeFTPSession(sftp)
                    #     utility.closeSSHConnection(client)

                    #     reboot_2_update = utility.check_gateway_firmware_version(gateway_file_version, local_path)
                    #     if reboot_2_update:
                    #         os.system("reboot")

            except Exception as e:
                print(e)
                # if count_nError > 10:
                #     os.system("reboot")
                # else:
                #     count_nError = count_nError + 1
                #     print("Restart Network")
                #     os.system("poff rnet")
                #     time.sleep(1.0)
                #     powerToggle(75)
                #     time.sleep(15.0)
                #     check = checkSim7070g()
                #     os.system("pon rnet")
                #     time.sleep(10.0)

            try:
                file_firmware = glob.glob(gbl_path + "*.gbl")
                if file_firmware != []:
                    file_firmware = file_firmware[0]
                    new_firmware_version = file_firmware.split("_v")[1]
                    new_firmware_version = int(new_firmware_version.split(".")[0])
                    new_firmware_path = file_firmware
                    if new_firmware_version > old_firmware_version:
                        print("new firmware version: " + str(new_firmware_version))
                        old_firmware_version = new_firmware_version
            except Exception as e:
                print(e)
            
            if devices_to_connect != []:
                interface_index = 0
                for address in devices_to_connect:
                    print("connect to %s" % address)
                    devices_to_connect.remove(address)
                    if (address in map_config) or (address.upper() in map_config):
                        singleAgentConnection = Thread(target=connection, args=(address, map_config[address.upper()], new_firmware_version, interface_index))
                        interface_index = (interface_index + 1) % 2
                    else:
                        new_config[address.upper()] = default_config
                        singleAgentConnection = Thread(target=connection, args=(address, new_config[address.upper()], new_firmware_version, interface_index))
                        interface_index = (interface_index + 1) % 2
                    singleAgentConnection.daemon = True
                    singleAgentConnection.start()
            
            if device_ota_to_connect != []:
                for address in device_ota_to_connect:
                    print("connect to ota %s" % address)
                    device_ota_to_connect.remove(address)
                    singleAgentOtaConnection = Thread(target=otaConnection, args=(address, new_firmware_path, 0))
                    #interface_index = (interface_index + 1) % 2
                    singleAgentOtaConnection.daemon = True
                    singleAgentOtaConnection.start()
                    time.sleep(40.0)
            
            time.sleep(0.5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)
            
            
if __name__ == "__main__":
    main()
