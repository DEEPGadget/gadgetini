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

    # Connection start with Sender[Host]
    def connection_made(self, transport):
        self.transport = transport
        print("Serial Connenction start...") 

    # Send data to Host
    def send(self, data):
        packet = str(data) + '\n'
        self.transport.write(packet.encode())

    # Receive data from Host
    def data_received(self, data):
        self.buffer.extend(data)
        #print('data received', repr(self.buffer))
        # buffer iteration
        while b'\n' in self.buffer:
            # pop data using '\n' in buffer 
            line, _, self.buffer = self.buffer.partition(b'\n')
            data = line.decode(errors='ignore',encoding='utf-8').strip()
            print("Sender received data: {data}")
            self.handle_data(data)

    # Handle received data from Host 
    # parsing string to json insert gadgetini redis 
    def handle_data(self, data):
        key = ""
        value = ""
        if self.state == "INIT" and data == "SYN":
            print("Succesfully Received SYN by sender, send SYN-ACK")
            self.send("SYN-ACK")                
            self.state = "SYN-ACK_SENT"         
        elif self.state == "SYN-ACK_SENT" and data == "ACK":
            print("Succesfully Received ACK by sender, Connection ESTABLISHED")
            self.state = "CONNECTION_ESTABLISHED"  
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
                            #print("cpu   ", parsed_value)
                            #print("cpu   ", type(parsed_value))
                            
                            cpu_temp = parsed_value['Tctl']['temp1_input']
                            rd.set(cpu_key, cpu_temp)
                            #print("======")
                            #print("current key", cpu_key)
                            #print("current value", rd.get(cpu_key))

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

                            # set check
                            #print("======")
                            #print("current key", key)

                            #print(rd.get(key + '_gpu_name'))
                            #print(rd.get(key + '_gpu_temp'))
                            #print(rd.get(key + '_gpu_util'))
                            #print(rd.get(key + '_gpu_mem_util'))
                            #print(rd.get(key + '_gpu_power'))
                            #print(rd.get(key + '_gpu_power_limit'))

                        elif key.startswith('memory'):
                            total_mem = parsed_value['total_memory_gb']
                            avail_mem = parsed_value['available_memory_gb']
                            used_mem = parsed_value['used_memory_gb']
                            total_swp = parsed_value['swap_total_gb']
                            used_swp = parsed_value['swap_used_gb']
                            free_swp = parsed_value['swap_free_gb']
                            
                            rd.set('total_mem',total_mem)
                            rd.set('avail_mem',avail_mem)
                            rd.set('used_mem',used_mem)
                            rd.set('total_swp', total_swp)
                            rd.set('used_swp', used_swp)
                            rd.set('free_swp', free_swp)
                            # set check 
                            #print("======")
                            #print("current key", key)

                            #print(rd.get('total_mem'))
                            #print(rd.get('avail_mem'))
                            #print(rd.get('used_mem'))
                            #print(rd.get('total_swp'))
                            #print(rd.get('used_swp'))
                            #print(rd.get('free_swp'))

                        elif key.startswith('wormhole'):
                            vcore = parsed_value['vcore1']['in0_input']
                            asic1_temp = parsed_value['asic1_temp']['temp1_input']
                            power1 = parsed_value['power1']['power1_input']
                            current1 = parsed_value['current1']['curr1_input']

                            rd.set(key + '_vcore', vcore)
                            rd.set(key + '_asic_temp', asic1_temp)
                            rd.set(key + '_power', power1)
                            rd.set(key + '_current', current1)
                            # set check
                            #print("======")
                            #print("current key", key)
                            #print(rd.get(key + '_vcore'))
                            #print(rd.get(key + '_asic_temp'))
                            #print(rd.get(key + '_power'))
                            #print(rd.get(key + '_current'))

                        elif key.startswith('blackhole'):
                            vcore = parsed_value['vcore1']['in0_input']
                            asic1_temp = parsed_value['asic1_temp']['temp1_input']
                            power1 = parsed_value['power1_input']
                            current1 = parsed_value['curr1_input']

                            rd.set(key + '_vcore', vcore)
                            rd.set(key + '_asic_temp', asic1_temp)
                            rd.set(key + '_power', power1)
                            rd.set(key + '_current', current1)
                            # set check
                            #print(rd.get(key + '_vcore'))
                            #print(rd.get(key + '_asic_temp'))
                            #print(rd.get(key + '_power'))
                            #print(rd.get(key + '_current'))



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
    def connection_lost(self):
        print("Connection Lost")


async def main():
    loop = asyncio.get_running_loop()       
    await serial_asyncio.create_serial_connection(loop, ReceiverChunkProtocol, '/dev/ttyAMA0', baudrate=115200)
    await asyncio.Future()              
asyncio.run(main())

'''
host to gadgetini
redis k-v legend

  key        |   type/value
 cpu0_n            dict
 gpu0_n            dict
 cpu_util           dict
memory_util         dict
wormhole0_n        dict
blackhole0_n       dict

'''
