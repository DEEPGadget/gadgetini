import asyncio
import serial_asyncio
import redis
import json
import ast

rd = redis.StrictRedis(host='localhost', port=6379, db=0)

# Receiver[gadgetini]
class ReceiverChunkProtocol(asyncio.Protocol):

    def __init__(self):
        # serial data buffer
        self.buffer = bytearray()
        self.transport = None
        self.state = "INIT"
        self.loop = asyncio.get_running_loop()
        self.handshake_task = None
        self.closed = self.loop.create_future()

    # Connection start with Sender[Host]
    def connection_made(self, transport):
        self.transport = transport
        self.buffer.clear()
        print("Serial Connenction start...")
        self.start_handshake()

    # Send data to Host
    def send(self, data):
        packet = str(data) + '\n'
        if self.transport:
            self.transport.write(packet.encode())

    # Receive data from Host
    def data_received(self, data):
        self.buffer.extend(data)
        while b'\n' in self.buffer:
            line, _, self.buffer = self.buffer.partition(b'\n')
            data = line.decode(errors='ignore', encoding='utf-8').strip()
            if not data:
                continue
            print(f"Sender received data: {data}")
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
        print("Connection established with sender")
        self.state = "CONNECTION_ESTABLISHED"
        if self.handshake_task:
            self.handshake_task.cancel()
            self.handshake_task = None

    # Handle received data from Host
    # parsing string to json insert gadgetini redis
    def handle_data(self, data):
        key = ""
        value = ""
        if data == "SYN":
            print("Succesfully Received SYN by sender, send SYN-ACK")
            self.send("SYN-ACK")
            self.state = "SYN-ACK_SENT"
        elif data == "SYN-ACK":
            print("Received SYN-ACK from sender, replying with ACK")
            self.send("ACK")
            self.mark_established()
        elif data == "ACK" and self.state in {"SYN_SENT", "SYN-ACK_SENT"}:
            print("Succesfully Received ACK by sender, Connection ESTABLISHED")
            self.mark_established()
        elif self.state == "CONNECTION_ESTABLISHED":
            # receive string data from sender, string convert to dictionary.
            try:
                # 0 = default, inteager, float or just string
                # 1 = JSON
                # 2 = dictonary
                data_literal_flag = 0
                data_str = data.strip()
                # invalid data filtering
                if ':' not in data_str:
                    raise ValueError("Missing ':' in data, skipping... ", data_str)
                key, value = data_str.split(':', 1)
                key = key.strip()
                value = value.strip()

                # parsing JSON, dictionary literal
                if value.startswith('{') and value.endswith('}'):
                    try:
                        parsed_value = json.loads(value)
                        if key.startswith('cpu_'):
                            cpu_key = key + "_temp"
                            cpu_temp = parsed_value['Tctl']['temp1_input']
                            rd.set(cpu_key, cpu_temp)

                        elif key.startswith('gpu'):
                            name = parsed_value['name']
                            temp = parsed_value['temperature']
                            util = parsed_value['utilization_gpu']
                            util_mem = parsed_value['utilization_memory']
                            power_draw = parsed_value['power.draw']
                            power_limit = parsed_value['power.limit']

                            rd.set(key + '_gpu_name', name)
                            rd.set(key + '_gpu_temp', temp)
                            rd.set(key + '_gpu_util', util)
                            rd.set(key + '_gpu_mem_util', util_mem)
                            rd.set(key + '_gpu_power', power_draw)
                            rd.set(key + '_gpu_power_limit', power_limit)

                        elif key.startswith('memory'):
                            total_mem = parsed_value['total_memory_gb']
                            avail_mem = parsed_value['available_memory_gb']
                            used_mem = parsed_value['used_memory_gb']
                            total_swp = parsed_value['swap_total_gb']
                            used_swp = parsed_value['swap_used_gb']
                            free_swp = parsed_value['swap_free_gb']

                            rd.set('total_mem', total_mem)
                            rd.set('avail_mem', avail_mem)
                            rd.set('used_mem', used_mem)
                            rd.set('total_swp', total_swp)
                            rd.set('used_swp', used_swp)
                            rd.set('free_swp', free_swp)

                        elif key.startswith('wormhole'):
                            vcore = parsed_value['vcore1']['in0_input']
                            asic1_temp = parsed_value['asic1_temp']['temp1_input']
                            power1 = parsed_value['power1']['power1_input']
                            current1 = parsed_value['current1']['curr1_input']

                            rd.set(key + '_vcore', vcore)
                            rd.set(key + '_asic_temp', asic1_temp)
                            rd.set(key + '_power', power1)
                            rd.set(key + '_current', current1)

                        elif key.startswith('blackhole'):
                            vcore = parsed_value['vcore1']['in0_input']
                            asic1_temp = parsed_value['asic1_temp']['temp1_input']
                            power1 = parsed_value['power1_input']
                            current1 = parsed_value['curr1_input']

                            rd.set(key + '_vcore', vcore)
                            rd.set(key + '_asic_temp', asic1_temp)
                            rd.set(key + '_power', power1)
                            rd.set(key + '_current', current1)

                        data_literal_flag = 1

                    except json.JSONDecodeError:
                        parsed_value = ast.literal_eval(value)
                        data_literal_flag = 2
                # directly insert redis
                # cpu_util, server_ip, or not json format data
                else:
                    rd.set(key, value)
                    rst = rd.get(key)
                    print("key", key)
                    print("check set data", rst)
                print("current Data Literal: ", data_literal_flag)
            except redis.RedisError as e:
                print("Redis error ", e)
            except Exception as e:
                print("string to dictionary parsing error.", e)

    # Print when connection lost
    def connection_lost(self, exc):
        print("Connection Lost", exc)
        if self.handshake_task:
            self.handshake_task.cancel()
            self.handshake_task = None
        self.state = "INIT"
        if not self.closed.done():
            self.closed.set_result(None)

    def wait_closed(self):
        return self.closed


async def main():
    loop = asyncio.get_running_loop()
    while True:
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(loop, ReceiverChunkProtocol, '/dev/ttyAMA0', baudrate=115200)
            await protocol.wait_closed()
        except Exception as exc:
            print("Serial connection failed, retrying...", exc)
            await asyncio.sleep(2)
asyncio.run(main())
