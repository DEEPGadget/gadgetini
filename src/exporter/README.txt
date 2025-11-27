gadgetini Host Setup Manual

(Verified on Rocky Linux 8.9 & RHEL 10)

1. Rocky Linux 8.9
1.1 Common Setup (HOST / gadgetini 공용)
# 패키지 메타데이터 갱신
sudo dnf makecache

# 기본 패키지 설치
sudo dnf install -y \
  epel-release \
  redis \
  python311 python3.11-pip \
  screen \
  lm_sensors

# Redis 서비스 활성화 및 즉시 시작
sudo systemctl enable --now redis

# Python 3.11 환경에 필요한 패키지 설치
sudo python3.11 -m pip install \
  pyserial-asyncio \
  redis \
  jsons \
  rich

# (선택) python 대상을 선택
sudo update-alternatives --config python

# (선택) 기본 python 명령을 특정 버전에 연결
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.8 2

# 현재 사용자에게 시리얼 포트 접근 권한 부여
sudo usermod -aG dialout "$USER"


usermod 이후에는 로그아웃 후 재로그인이 필요합니다.

1.2 HOST: USB 시리얼(FT232) 권한 설정

벤더/제품 ID 확인

udevadm info -a -n /dev/ttyUSB0 | grep -E 'idVendor|idProduct'


예시 출력:

ATTRS{idProduct}=="6001" ATTRS{idVendor}=="0403" ATTRS{idProduct}=="0002" ATTRS{idVendor}=="1d6b"


udev 규칙 작성

sudo vim /etc/udev/rules.d/99-ttyusb-permissions.rules


내용:

SUBSYSTEM=="tty", KERNEL=="ttyUSB[0-9]*", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE:="0660", GROUP:="dialout"


규칙 리로드 및 적용

sudo udevadm control --reload-rules
sudo udevadm trigger


권한 확인

ls -al /dev/ttyUSB0


예시:

crw-rw---- 1 root dialout 188, 0 Nov 21 02:43 /dev/ttyUSB0

2. RHEL 10
2.1 Common Setup (HOST / gadgetini 공용)

NVIDIA repo 추가 및 드라이버 설치

sudo dnf config-manager --add-repo \
  https://developer.download.nvidia.com/compute/cuda/repos/rhel10/x86_64/cuda-rhel10.repo

sudo dnf clean all
sudo dnf -y install nvidia-open


기본 패키지 설치

sudo dnf makecache

sudo dnf install -y \
  screen \
  tmux \
  lm_sensors \
  keydb \
  git


KeyDB 서비스 활성화

sudo systemctl enable --now keydb


screen 소켓 디렉터리 권한 조정

sudo chmod 777 /run/screen


Python 패키지 설치

pip3 install \
  pyserial-asyncio \
  redis \
  jsons \
  rich

2.2 /dev/ttyUSB0 미인식 시 트러블슈팅
2.2.1 커널 모듈 로드
# FTDI USB-Serial 드라이버 로드
sudo modprobe ftdi_sio

2.2.2 kernel-modules-extra 패키지 확인 및 설치
rpm -qa | grep "kernel-modules-extra-$(uname -r)"


결과가 아무 것도 안 나오면 설치:

sudo dnf install "kernel-modules-extra-$(uname -r)"


설치 후 모듈 다시 로드:

sudo modprobe usbserial
sudo modprobe ftdi_sio


디바이스 확인:

ls /dev | grep ttyUSB

2.2.3 여전히 /dev/ttyUSB0 가 안 보일 때 (USB 포트 전원 리셋)

uhubctl 사용 예시:

sudo uhubctl -l 1-1 -p 2 -a off
sleep 1
sudo uhubctl -l 1-1 -p 2 -a on


또는 시스템 재부팅.

2.3 RHEL 10: 시리얼 디바이스 권한 설정 (예: /dev/ttyAMA0)

udev 규칙 작성

sudo vim /etc/udev/rules.d/99-ttyUSB-permissions.rules


내용:

SUBSYSTEM=="tty", KERNEL=="ttyAMA0", MODE:="0777"


실제 환경에 맞게 ttyAMA0 대신 ttyUSB0 등으로 변경 가능.

규칙 리로드 및 적용

sudo udevadm control --reload-rules
sudo udevadm trigger

3. 그룹 권한 참고

시리얼 디바이스 접근을 위해, 사용하는 계정을 관련 그룹에 추가해야 할 수 있습니다:

# 예시: dialout 그룹 사용 시
sudo usermod -aG dialout <username>

# 또는 uucp 그룹 사용하는 배포판의 경우
sudo usermod -aG uucp <username>


그룹 변경 후에는 반드시 로그아웃 후 재로그인 또는 재부팅이 필요합니다.
