from bluepy3 import btle
from datetime import datetime

class myDelegateNotify(btle.DefaultDelegate):
    def __init__(self, address):
        btle.DefaultDelegate.__init__(self)
        self.error = False
        self.counter = 0
        self.address = address
        self.data_shock = ''
        self.data_periodic = ''
        self.data_shock_received = False
        self.data_periodic_received = False
        now = datetime.now()
        now_string = now.strftime("%Y%m%d_%H%M%S")
        self.file_name_shock = "Data/" + self.address.replace(":", "") + "_" + now_string + "_shock.bin"
        self.file_name_periodic = "Data/" + self.address.replace(":", "") + "_" + now_string + "_periodic.bin"
    
    def handleNotification(self, cHandle, data):
        data_len = len(data)
        packID = ord(data[0]) + (ord(data[1]) << 8)
        if packID == 0:
            self.counter = 0
        else:
            if self.counter + 1 != packID:
                print("ERROR, missing packet %u" % (self.counter + 1))
                self.counter = packID
            else:
                self.counter = self.counter + 1
            
        pack2Receive = (ord(data[3]) + (ord(data[4]) << 8)) - 1
        if data[2] == "\x01": # Shock data packet type
            print("shock %u, %u/%u" % (data_len, packID, pack2Receive))
            self.data_shock += ''.join(data[5:])
            if packID == pack2Receive: # Last shock data packet received
                print("shock received")
                self.data_shock_received = True      
        elif data[2] == "\x02": # Periodic data packet type
            print("%s %u, %u/%u" % (self.address, data_len, packID, pack2Receive))
            #with open(self.file_name_periodic, 'a') as file_periodic:
                #file_periodic.write(data[5:])
                #file_periodic.close()
            self.data_periodic += ''.join(data[5:])
            if packID == pack2Receive: # Last periodic data packet received
                print("periodic received")
                self.data_periodic_received = True
        else:
            self.error = True
    
    
class myDelegateScanner(btle.DefaultDelegate):
    def __init__(self):
        btle.DefaultDelegate.__init__(self)
        self.addr = []
        self.addrData = []
        
    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            self.addr.append(dev.addr)
        if isNewData:
            self.addrData.append(dev.addr)
            
            
class agentNotify():
    def __init__(self, address, interface):
        self.device = btle.Peripheral(address, iface=interface)
        self.address = address
        self.scanner = None
        self.response = None
        self.scanned_devices = None
       
       
    def bleConnect(self, address):
        self.device = btle.Peripheral(address)
    
    
    def bleDelegate(self, delegate):
        self.device.withDelegate(delegate)
        
        
    def bleSetMTU(self, size):
        self.device.setMTU(size)
        
        
    def bleWriteCh(self, handler, data, response):
        self.response = self.device.writeCharacteristic(handler, data, response)
        if response:
            return self.response
    
    def bleReadCh(self, handler):
        self.response = self.device.readCharacteristic(handler)
        return self.response
        

class agentScanner():
    def __init__(self, bt_antenna):
        self.scanner = btle.Scanner(bt_antenna) #1 for external, 0 for internal
        self.scanner.withDelegate(myDelegateScanner())
        
    def bleScan(self, time):
        self.scanned_devices = self.scanner.scan(time)
        
    def bleScan_v2(self, time):
        self.scanner = btle.Scanner()
        self.scanner.withDelegate(myDelegateScanner())
        self.scanner.start()
        self.scanner.process(time)
        self.scanner.stop()
        return self.scanner.getDevices()