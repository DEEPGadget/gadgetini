import subprocess
import psutil
import time
from prometheus_client import start_http_server, Gauge

# Prometheus Gauge CPU Utilization Metrics
cpu_user_usage = Gauge('cpu_user_usage_percent', 'CPU usage by user mode')
cpu_system_usage = Gauge('cpu_system_usage_percent', 'CPU usage by system mode')
cpu_nice_usage = Gauge('cpu_nice_usage_percent', 'CPU usage by nice processes')
cpu_idle_usage = Gauge('cpu_idle_usage_percent', 'CPU idle time')
cpu_total_usage = Gauge('cpu_total_usage_percent', 'Total CPU usage')

# Prometheus Gauge CPU Temperature Metrics
cpu_tctl_temp_gauge = Gauge('cpu_tctl_temperature_celsius', 'CPU Tctl Temperature in Celsius')

def collect_cpu_metrics():
    # interval 1 second
    cpu_times = psutil.cpu_times_percent(interval=1, percpu=False)

    # each CPU Utilization (user, system, nice, idle)
    user_usage = cpu_times.user
    system_usage = cpu_times.system
    nice_usage = cpu_times.nice
    idle_usage = cpu_times.idle

    # total CPU Utilization (user + system + nice)
    total_usage = user_usage + system_usage + nice_usage

    # Update Prometheus Metrics
    cpu_user_usage.set(user_usage)
    cpu_system_usage.set(system_usage)
    cpu_nice_usage.set(nice_usage)
    cpu_idle_usage.set(idle_usage)
    cpu_total_usage.set(total_usage)

def get_tctl_temperature():
    """get tctl temperature (sensors command)"""
    try:
        # Run sensors command
        result = subprocess.run(['sensors'], stdout=subprocess.PIPE)
        output = result.stdout.decode('utf-8')

        # get Tctl information
        for line in output.splitlines():
            if 'Tctl:' in line:
                temp_str = line.split()[1]  # only get temperature
                temp_value = float(temp_str.replace('°C', ''))  # change numeric
                return temp_value

    except Exception as e:
        print(f"Error while reading Tctl temperature: {e}")
        return None

if __name__ == "__main__":
    # Prometheus HTTP server start (port 8889)
    start_http_server(8889)

    # interval 1 second, send data
    while True:
        collect_cpu_metrics()

        temp = get_tctl_temperature()
        if temp is not None:
            cpu_tctl_temp_gauge.set(temp)
        time.sleep(1)


