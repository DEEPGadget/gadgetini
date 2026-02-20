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
        self.handshake_task = None
        self.data_task = None
        self.loop = asyncio.get_running_loop()
        self.closed = self.loop.create_future()

    # Connection start with Receiver[gadgetini]
    def connection_made(self, transport):
        self.transport = transport
        self.buffer.clear()
        print("Serial Connenction start...")
        self.start_handshake()

    # Send data to gadgetini
    def send(self, data):
        packet = str(data) + '\n'
        print("send()", packet)
        if self.transport:
            self.transport.write(packet.encode())

    # Receive data from gadgetini
    def data_received(self, data):
        self.buffer.extend(data)
        while b'\n' in self.buffer:
            line, _, self.buffer = self.buffer.partition(b'\n')
            data = line.decode(errors='ignore').strip()
            if not data:
                continue
            self.handle_data(data)

    def start_handshake(self):
        if self.handshake_task:
            self.handshake_task.cancel()
        self.state = "INIT"
        self.handshake_task = self.loop.create_task(self._syn_loop())

    async def _syn_loop(self):
        while self.state != "CONNECTION_ESTABLISHED":
            self.send("SYN")
            if self.state == "INIT":
                self.state = "SYN_SENT"
            await asyncio.sleep(1)

    def mark_established(self):
        if self.state == "CONNECTION_ESTABLISHED":
            return
        print("Connection established, start sending data")
        self.state = "CONNECTION_ESTABLISHED"
        if self.handshake_task:
            self.handshake_task.cancel()
            self.handshake_task = None
        if not self.data_task:
            self.data_task = self.loop.create_task(self.send_data_loop())

    # Handle received data from gadgetini
    def handle_data(self, data):
        if data == "SYN":
            print("Received SYN from peer, replying with SYN-ACK")
            self.send("SYN-ACK")
            self.state = "SYN_RECEIVED"
        elif data == "SYN-ACK":
            print("Succesfully Received SYN-ACK by receiver, send ACK")
            self.send("ACK")
            self.mark_established()
        elif data == "ACK" and self.state in {"SYN_SENT", "SYN_RECEIVED"}:
            print("Received ACK, connection established")
            self.mark_established()
        elif self.state == "CONNECTION_ESTABLISHED":
            # ignore payload echoed back to sender
            print(f"Received data while established: {data}")

    def stop_tasks(self):
        for task in (self.handshake_task, self.data_task):
            if task:
                task.cancel()
        self.handshake_task = None
        self.data_task = None
        self.state = "INIT"

    # Print when connection lost
    def connection_lost(self, exc):
        print("Connection Lost", exc)
        self.stop_tasks()
        if not self.closed.done():
            self.closed.set_result(None)

    def wait_closed(self):
        return self.closed

    # Send dummy data every 1sec
    async def send_data_loop(self):
        while True:
            try:
                data = ""
                for wildkey in rd.scan_iter():
                    key = wildkey.decode('utf-8')
                    print("getting data using key: ", key)
                    buf = rd.get(key)
                    if buf is None:
                        continue
                    data = data + key + ':' + buf.decode('utf-8') + '\n'
                self.send(data)
                self.counter += 1
            except redis.RedisError as exc:
                print("Redis error while reading data", exc)
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
    while True:
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(loop, InputChunkProtocol, '/dev/ttyUSB0', baudrate=115200)
            await protocol.wait_closed()
        except Exception as exc:
            print("Serial connection failed, retrying...", exc)
            await asyncio.sleep(2)
asyncio.run(main())
