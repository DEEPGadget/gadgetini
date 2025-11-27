import asyncio
import serial_asyncio
import redis

rd = redis.StrictRedis(host='localhost', port=6379, db=0)

# Sender[Host]
class InputChunkProtocol(asyncio.Protocol):

    def __init__(self):
        # serial data buffer
        self.buffer = bytearray()
        self.transport = None
        self.state = "INIT"
        self.counter = 0

    # Connection start with Receiver[gadgetini]
    def connection_made(self, transport):
        self.transport = transport
        self.send("SYN")            # Send SYN Sender[Host] to Receiver[gadgetini]
        print("Serial Connenction start...") 
        self.state = "SYN_SENT"     # Switch state INIT -> SYN_SENT after send SYN to Receiver[gadgetini]

    # Send data to gadgetini
    def send(self, data):
        packet = str(data) + '\n'
        print("send()",packet)
        self.transport.write(packet.encode())

    # Receive data from gadgetini
    def data_received(self, data):
        self.buffer.extend(data)
        #print('data received', repr(self.buffer))
        # buffer iteration
        while b'\n' in self.buffer:
            # pop data using '\n' in buffer 
            line, _, self.buffer = self.buffer.partition(b'\n')
            data = line.decode(errors='ignore').strip()
            #print("Sender received data: {data}")
            self.handle_data(data)

    # Handle received data from gadgetini
    def handle_data(self, data):
        if self.state == "SYN_SENT" and data == "SYN-ACK":  # When received SYN-ACK from Receiver[gadgetini]
            print("Succesfully Received SYN-ACK by reciever, send ACK")
            self.send("ACK")                        # Send ACK Sender[Host] to Receiver[gadgetini]
            self.state = "CONNECTION_ESTABLISHED"   # Switch state SYN_SENT -> CONNECTION_ESTABLISHED after send ACK to Receiver[gadgetini]
            asyncio.create_task(self.send_data_loop())
   
    # Print when connection lost
    def connection_lost(self):
        print("Connection Lost")

    # Send dummy data every 1sec
    async def send_data_loop(self):
        while True:
            data = ""
            for wildkey in rd.scan_iter():
                key = wildkey.decode('utf-8')
                print("getting data using key: ",key)
                buf = rd.get(key).decode('utf-8')
                #print("buf", buf)
                data = data + key + ':' + buf + '\n'
            #print(data)
            self.send(data)
            self.counter += 1
            await asyncio.sleep(3)

'''
host to gadgetini
redis k-v legend

  key        |   type/value
    cpukeys = rd.keys('cpu_*')
    gpukeys = rd.keys('gpu_*')
    whkeys = rd.keys('wormhole_*')
    bhkyes = rd.keys('blackhole_*')
    cputil = rd.keys('cpu_util')
    memutil = rd.keys('memory_util')
    # multi devices iteration.
    # append to data, \n is seperator. 
    for cpu in cpukeys:
        buf = rd.get(cpu).decode('utf-8')
        data = data + buf + '\n'
        print("CPU data ", data)
    for gpu in gpukeys:
        buf = rd.get(gpu).decode('utf-8')
        data = data + buf + '\n'
        print("GPU key", gpuk)
    for wh in whkeys:
        buf = rd.get(wh).decode('utf-8')
        data = data + buf + '\n'
    for bh in bhkeys:
        buf = rd.get(bh).decode('utf-8')
        data = data + buf + '\n'
 
'''



async def main():
    loop = asyncio.get_running_loop()           # Use event loop as variable loop
    await serial_asyncio.create_serial_connection(loop, InputChunkProtocol, '/dev/ttyUSB0', baudrate=115200)
    await asyncio.Future()          # Keep event loop
asyncio.run(main())
