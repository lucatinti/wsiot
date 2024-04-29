import paramiko
import os
import ftplib

#port = 2022
#username = "wisepower"
#password = "wisepower!"

def openSSHConnection(address, port, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(address, port=port, username=username, password=password)
    return client


def openFTPSession(client):
    sftp = client.open_sftp()
    return sftp


def closeSSHConnection(client):
    client.close()


def closeFTPSession(client):
    closeSSHConnection(client)
    

def saveDataIntoServer(client, localpath, remotepath):
    client.put(localpath, remotepath)


def updateAlarmFileIntoServer(client):
    alarm_f = open("/home/rock/Documents/alarm.txt")
    alarm_text = alarm_f.read()
    if alarm_text != "":
        file_handle = client.file("/home/wisepower/files_wisepower/alarm.txt", mode='a', bufsize=1)
        file_handle.write(alarm_text)
        file_handle.flush()
        file_handle.close()
    alarm_f.close()

def getConfigFile(sftp, localpath, remotepath, map_c, new_c):    
    sftp.get(remotepath, localpath)
    d = map_c
    try:
        with open(localpath, 'r') as f:
            config_list = []
            stop = False
            while not stop:
                line = f.readline()[:-1]
                if line == '': stop = True
                else: config_list.append(line.split(" "))
                
                for x in config_list:
                    d[x[0]] = x[1:]
            f.close()
            
        with sftp.file(remotepath, 'a') as fr:
            for addr in new_c:
                if addr.upper() not in d:
                    string2write = addr.upper()
                    for i in range(len(new_c[addr])):
                        string2write += " "+new_c[addr][i]
                    fr.write(string2write+"\n")
            fr.close()
    except Exception as e:
        print("Error in getConfigFile: "+str(e))
    return d


def getFirmwareFile(sftp, localpath, remotepath):
    try:
        sizeGblLocal = 0
        file_firmware = os.listdir(localpath)
        if file_firmware != []:
            file_firmware = file_firmware[0]
            sizeGblLocal = os.stat(localpath+file_firmware).st_size
        filename = str(sftp.listdir(remotepath)[0])
        sizeGblRemote = sftp.stat(remotepath+filename).st_size
        print(sizeGblLocal, sizeGblRemote)
        if filename != file_firmware or (filename == file_firmware and sizeGblRemote != sizeGblLocal):
            os.system("rm " + localpath + "*")
            sftp.get(remotepath+filename, localpath+filename)
            sizeGblLocal = os.stat(localpath+filename).st_size
            print(sizeGblLocal)
            if sizeGblLocal != sizeGblRemote:
                print("Remove glb file, download not completed")
                os.system("rm " + localpath + "*")
    except Exception as e:
        print("Error in getFirmwareFile: " + str(e))


def check_gateway_firmware_version(firmware_version, path):
    reboot2update = False
    actual_version = int(firmware_version.split("-")[-1])

    try:
        session = ftplib.FTP()
        session.connect("ftp.wisepower.it", 21, 60)
        session.login("1451303@aruba.it", "QWEasz123*")
        session.cwd("www.wisepower.it/ws_iot/Gateway")
        stored_folder = session.nlst()[2]
        stored_version = int(stored_folder.split("-")[-1])

        if actual_version < stored_version:
            reboot2update = True
            session.cwd(stored_folder)
            stored_files = session.nlst()[2:]
            for f in stored_files:
                with open(path+f, "w") as fp:
                    session.retrbinary('RETR %s' % f, fp.write)

        session.quit()
    except Exception as e:
        print("Error during FTP aruba connection: ", str(e))

    return reboot2update
