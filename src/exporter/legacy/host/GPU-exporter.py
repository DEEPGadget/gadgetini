import subprocess
import time
from prometheus_client import start_http_server, Gauge

# Prometheus Gauges for GPU Metrics
gpu_temperature = Gauge('gpu_temperature_celsius', 'GPU Temperature in Celsius', ['gpu_id'])
gpu_utilization = Gauge('gpu_utilization_percent', 'GPU Utilization Percentage', ['gpu_id'])

def collect_gpu_metrics():
    """Collect GPU metrics using nvidia-smi command."""
    try:
        # Run nvidia-smi command
        result = subprocess.run(['nvidia-smi', '--query-gpu=index,temperature.gpu,utilization.gpu',
                                 '--format=csv,noheader,nounits'], stdout=subprocess.PIPE)
        output = result.stdout.decode('utf-8')

        # Parse the output and update Prometheus metrics
        for line in output.strip().split('\n'):
            gpu_id, temp, util = line.split(', ')
            gpu_temperature.labels(gpu_id=gpu_id).set(float(temp))
            gpu_utilization.labels(gpu_id=gpu_id).set(float(util))

    except Exception as e:
        print(f"Error while collecting GPU metrics: {e}")

if __name__ == "__main__":
    # Start Prometheus HTTP server on port 8890
    start_http_server(8890)

    # Collect metrics every second
    while True:
        collect_gpu_metrics()
        time.sleep(1)
