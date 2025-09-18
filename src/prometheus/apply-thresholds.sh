(base) jyeongmu@jyeongmu:~/gadgetini/src/prometheus$ cat apply-thresholds.sh
#!/bin/bash
set -euo pipefail

set -a
source /home/jyeongmu/gadgetini/src/prometheus/thresholds.env
set +a

envsubst < /home/jyeongmu/gadgetini/src/prometheus/rules.tmpl \
  > /home/jyeongmu/gadgetini/src/prometheus/rules.yml

promtool check rules /home/jyeongmu/gadgetini/src/prometheus/rules.yml
sudo systemctl restart prometheus

echo "Reloaded Prometheus."
