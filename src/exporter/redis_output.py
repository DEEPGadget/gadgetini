import redis

rd = redis.StrictRedis(host='localhost', port=6379, db=0)

while True:
    print(rd.get("coolant_temp"))
    print(rd.get("coolant_leak"))
    print(rd.get("coolant_level"))
    print(rd.get("air_temp"))
    print(rd.get("air_humit"))
    print(rd.get("chassis_stabil"))

 
