# Collector 통합 설계 — pcb_bootstrap + control_board → data_crawler 단일화

> **Status**: Design v2 (전원 아키텍처 재설계 반영).
> v1의 자율 냉각 상태 머신은 폐기 — 사유는 [§ 전원 아키텍처 결정](#전원-아키텍처-결정-v1--v2) 참조.

## Context

Gadgetini는 세대를 거치며 sensor 수집 경로가 분기되어 왔다:

| 세대 | Machine | Sensor 백엔드 | Coolant 채널 |
|---|---|---|---|
| Gen1 | dg5w | ADS1256 SPI | inlet1 only |
| Gen2 | dg5w | ADS1256 SPI | inlet1 + outlet1 (일부 unit) |
| Gen2 | dg5r | ADS1256 SPI | inlet1/2 + outlet1/2 |
| Gen3 | dg5w | PCB Modbus RTU | inlet1 + outlet1 (확장 가능) |
| Gen3 | dg5r | PCB Modbus RTU | inlet1/2 + outlet1/2 |

**현재 구조**: Gen1~2는 `data_crawler.service` (ADS1256 직접 read), Gen3는 `control_board.service` (PCB Modbus). 부팅 시 `pcb_bootstrap.service`가 PCB 감지 → control_board start → systemd `Conflicts=`로 data_crawler 자동 정지.

**문제점**:
- 동일 image가 신/구 hw 모두에서 동작해야 한다는 정책이 코드 레벨이 아닌 **systemd 안무**로 구현됨
- 채널 매핑이 두 곳에 분산: legacy는 [machine_config.py:13-16](machine_config.py#L13-L16), PCB는 [../control_board/config.yaml의 wiring 섹션](../control_board/config.yaml#L46-L70)
- 신 sub-variant 추가 시 두 코드베이스 다 수정
- ADS1256 init이 module import 시점에 무조건 실행 → PCB 시스템에서 `import dlc_sensors` 실패

**목표**: 단일 collector 코드 (`data_crawler.py`) + 단일 service (`data_crawler.service`). 모든 변형(machine type × backend × wiring)을 **machine_config.py 한 곳**에서 선언. config.ini는 사용자 향(machine 식별 + 카운트만), 사용자는 변천사 모름.

---

## 전원 아키텍처 결정 (v1 → v2)

### v1 가정 (폐기)

이전 draft는 다음을 전제로 했음:
- PDB에서 12V 독립 전원이 PCB로 항상 공급됨 (메인보드 OFF여도 PCB 살아 있음)
- PCB가 idle 펌프(10%) + idle 팬(8%)을 STANDBY에서도 구동 → NTC 신호 amplify
- 냉각수 온도 기반 자율 STANDBY/ACTIVE 상태 머신으로 액추에이터 자율 제어

### 무엇이 잘못됐나

- **PDB가 SB12V를 제공하지 않음** — 메인보드 OFF 시 PCB도 OFF
- 설령 SB12V가 있다 해도 idle 펌프/팬 구동 전력을 standby 라인에서 끌어올 수 없음
- → v1의 "PCB 항상 켜짐 + 자율 냉각" 시나리오 자체가 실현 불가

### v2 결정 (제조사와 합의된 신규 방향)

**제어보드 리비전으로 5V 상시 + 12V 스위치드 분리 전원 도입** (ATX 패턴):

| 도메인 | 공급원 | 항상 ON | 용도 |
|---|---|---|---|
| **5VSB** | 별도 standby 라인 | ✓ | PCB MCU + 모든 센서 |
| **12V 스위치드** | 메인보드 12V (서버 ON 시만) | — | 펌프/팬 드라이브, MOSFET, fan tach 풀업 |

**공통 GND**는 두 도메인이 공유.

**자연스러운 하드웨어 인터록**: 12V 부재 시 MCU가 PWM 출력해도 액추에이터 무동작. **firmware에서 enable 게이팅 로직 불필요** — STANDBY/ACTIVE 상태 머신 폐기 가능.

### 리비전 작업량

ATX 메인보드 표준 패턴이라 재설계가 아닌 moderate revision:

| 항목 | 변경 |
|---|---|
| 입력 커넥터 | 5VSB 핀 추가 |
| 전원 회로 | 5VSB → 3.3V LDO 1개 추가 (MCU 상시 전원) |
| 전원 플레인 | 5V / 12V split plane |
| MOSFET / 게이트 드라이버 | 그대로 (12V 도메인) |
| 도메인 경계 신호 | tach/일부 IO에 레벨시프터 또는 풀업 추가 |
| 펌웨어 | 단순화 — 상태 머신 삭제 |

PCB 1~2 rev cycle, BOM 2~3개 추가. 케이스/메커니컬 변경 없음.

---

## 현재(리비전 전) 하드웨어 스펙

본 통합 작업이 1차로 타겟하는 상태 — 리비전 적용 전:

- **PCB 전원**: 메인보드 12V 단일 입력 (메인보드 OFF → PCB OFF)
- **PCB 센서 범위**: NTC × N (coolant), leak, level, flow, **air_temp, air_humit 포함**
- **Pi 직결 센서**: ADS1256 (Gen1~2 한정), MPU6050 (dg5w 한정 chassis_stabil)
- **데이터 경로**: PCB → Modbus → Pi (Redis) → exporter / display
- **Cooling**: 메인보드 ON 시점부터 펌프 60% + fan_curve. STANDBY 개념 없음 (전원 자체가 없음)

→ 본 통합 작업은 리비전 전·후 모두에서 동작. 리비전 이후 추가 변경은 [§ 리비전 후 변경 예상](#리비전-후-변경-예상) 참조.

---

## 통합 후 책임 분담 (Where each thing lives)

### `display/config.ini` (사용자가 편집, web UI 연동)

**역할 변화 없음** — minimal user-facing config.

```ini
[PRODUCT]
name=dg5r              # 'dg5w' | 'dg5r'
gpu_count=8
cpu_count=2
fan_count=2
```

**원칙**: Wiring/채널/backend 같은 hw 변천사 정보는 **여기 절대 추가하지 않음**.

### `exporter/machine_config.py` — 두 backend 모두 머신별 매핑

PCB와 Legacy가 동일한 패턴(`{머신: {logical: 채널}}`)을 가지는 두 개의 평행 dict.

```python
# 기존 (변경 없음)
MACHINE = _cfg.get('PRODUCT', 'name', fallback='unknown').lower()
GPU_COUNT = _cfg.getint('PRODUCT', 'gpu_count', fallback=8)
CPU_COUNT = _cfg.getint('PRODUCT', 'cpu_count', fallback=2)

# Legacy ADS1256 채널 매핑 (현 상태 유지)
COOLANT_CHANNELS = {
    'dg5w': {'inlet1': 4, 'outlet1': 5},
    'dg5r': {'inlet1': 2, 'outlet1': 3, 'outlet2': 4, 'inlet2': 5},
}

# PCB Modbus NTC 채널 매핑 (신규)
COOLANT_CHANNELS_PCB = {
    'dg5w': {'inlet1': 13, 'outlet1': 14},
    'dg5r': {'inlet1': 13, 'outlet1': 14, 'outlet2': 15, 'inlet2': 16},
}
```

**원칙**:
- **config.ini의 machine 타입(`name=dg5r`)이 진실의 source.**
- **data_crawler.py는 선언된 채널을 read하고 Redis SET.** dict 선언이 곧 wiring 명세.
- 새 (machine, backend) 조합 등장 시 dict에 한 줄 추가.

### `exporter/data_crawler.py` — 단일 entrypoint

```python
import dlc_sensors
from pcb_driver import probe_pcb           # None or PCBDriver 반환
from pcb_control import FanCurveController

def main():
    rd = redis.StrictRedis(...)

    # 1. PCB probe FIRST — cfg 의존성 없음
    pcb = probe_pcb()
    log.info("PCB detected" if pcb else "no PCB — legacy ADS1256 path")

    # 2. PCB일 때만 운용 config + cooling controller
    cfg = None
    controller = None

    if pcb is not None:
        cfg = load_pcb_config()
        controller = FanCurveController(pcb, cfg)
        controller.cold_start_kick(cfg['fan_cold_start'])

    cycle_s = cfg['loop']['cycle_seconds'] if cfg else 1.0

    while True:
        # 센서 read — PCB면 Modbus (env 포함), 없으면 ADS1256 + Pi env
        if pcb is not None:
            pcb.poll(rd)                 # Modbus → coolant_*, leak, level, air_temp, air_humit, comm_status
        else:
            dlc_sensors.poll_coolant(rd) # ADS1256 → coolant_*, leak, level
            dlc_sensors.update_env(rd)   # I2C/GPIO → air_temp, air_humit (Legacy hw 한정)

        # MPU6050 chassis_stabil — Pi 직결 그대로 (리비전 후 PCB 이관 예정)
        dlc_sensors.update_chassis(rd)

        # 액추에이터 명령 (PCB path 한정. 12V 부재 시 무동작 — hw 인터록)
        if controller is not None:
            controller.update(rd)        # fan_curve + pump 60%

        sleep(cycle_s)

if __name__ == '__main__':
    main()
```

**v1 대비 단순화**:
- `CoolingStateTracker` 폐기 (상태 머신 자체가 없음)
- `controller.standby(rd)` 분기 없음 — 항상 단일 명령 경로
- `cooling_state` Redis 키 폐기 (필요 시 단순 `'on' | 'off'`로 축소, 12V tach 살아있으면 'on')

**왜 probe가 cfg 로드보다 먼저?**:
- Legacy hw (ADS1256)에서는 pcb_config.yaml 내용 거의 전부가 무의미
- driver 결정 전 cfg 로드는 낭비 + 의미 혼란
- Probe 자체는 하드코딩 default (port/baud)로 충분

**컴포넌트 존재 조건**:

| 컴포넌트 | 항상 존재 | PCB일 때만 |
|---|---|---|
| `driver` (PCBDriver 또는 ADS1256Driver) | ✓ | — |
| `cfg` (pcb_config.yaml dict) | — | ✓ |
| `controller` (FanCurveController) | — | ✓ |

> NoOp 패턴 안 씀 — `controller is None` 직접 비교가 더 명료.

**`probe_pcb()` 동작** (현 [../control_board/pcb_bootstrap.py](../control_board/pcb_bootstrap.py) 로직 흡수):

```
1. /dev/serial0 + /dev/ttyUSB0 에 각각 baud 115200, 9600 순회로
   Modbus FC04 read_input_registers(0, 1) 시도
        │
        ├─ 어떤 조합에서 응답 있음 → PCB 장착 확정 → return PCBDriver(...)
        └─ 모두 응답 없음 → 구hw 추정 → return ADS1256Driver(...)
```

**Probe는 부팅 시 1회만**. 장착된 PCB는 빠지지 않으므로 runtime 재probe (구 `pcb_watcher.service` 역할) 불필요. 일시 통신 끊김은 `comm_status` Redis 키에서 별도로 추적.

### Cooling control (v2 — 단순화)

**상태 머신 없음**. PCB가 살아 있는 동안에는 항상 동일 명령 송신:

| 항목 | 값 | 근거 |
|---|---|---|
| 펌프 duty | 60% fixed | 유량 센서 없음 → fixed-duty 운용 정책 |
| 팬 duty | fan_curve (8~100%) | outlet 30°C → 8%, 60°C → 100% 선형 |
| 부팅 시 fan cold start kick | 10% × 3초 → 8% 정착 | 실측 검증 stall 회피 |
| 30°C alert 임계 | ASHRAE W3 공급수 상한 근사 | **alert only** — 제어 아닌 모니터링 |

**v1에서 폐기된 항목**:
- STANDBY/ACTIVE 상태 머신
- ΔT 1°C 활성화 임계
- Asymmetric hysteresis (27°C 복귀, 0.3°C, 30분 grace, 30분 hold)
- STANDBY pump 10% / fan 8% 분기 (fan 8%는 fan_curve min_duty로 흡수)
- 자율 ΔT 기반 부하 감지

**왜 폐기?** — 12V가 메인보드 의존이라 STANDBY 시점에 액추에이터 자체가 OFF. "느리게 돌릴까 빠르게 돌릴까"의 선택지가 없음 (binary on/off).

### NTC noise baseline (참고 — 여전히 유효)

ΔT 1°C 임계가 사라졌지만 노이즈 baseline 실측치는 향후 모든 임계값 결정의 참고 자료로 남김.

**실측 노이즈**:
- 단일 NTC stdev: 0.025~0.041°C
- ΔT stdev: 0.045°C

향후 alert/threshold 결정 시 노이즈 floor의 6~22배 마진을 가이드로 사용.

### Fan 8% 근거 (참고)

fan_curve `min_duty = 8%` 인 이유 (0% 정지 아닌 영구 회전):

1. **Cold start stall 회피** — 4-pin PWM 팬은 정지 후 재시동 시 베어링 정지마찰 + PWM low duty 토크 부족으로 stall 또는 시동 잡음 발생. 영구 회전이면 회전 관성 유지 → stall 원천 차단.
2. **무음 수준** — 8% duty ≈ 1500 RPM, ≈25 dBA. 정숙한 사무실(30~35 dBA)보다 조용해 사실상 무음.
3. **Cold start kick 실측** — 부팅 직후 stall 회피를 위해 10% × 3초 kick 후 8% 정착. 10%가 실측 검증된 cold start 최소 duty. 일단 회전 시작하면 8%로도 유지 가능 (kinetic friction < static friction).

리비전 후에도 동일 — 12V 공급 직후 (메인보드 ON) cold start kick → fan_curve min 8% 유지.

### `exporter/dlc_sensors.py` — Legacy 백엔드 전용으로 축소

**현재(리비전 전) 스펙에서 PCB가 air_temp/air_humit를 직접 센싱**하므로 dlc_sensors.py의 env 함수는 **Legacy hw (PCB 미장착, Gen1~2) 한정**으로만 의미를 가진다.

| 함수 | PCB path | Legacy path |
|---|---|---|
| `get_coolant_temp` | 사용 안 함 (PCB가 IR로 노출) | 사용 |
| `get_coolant_leak/level_detection` | 사용 안 함 | 사용 |
| `get_air_temp` / `get_air_humit` | **사용 안 함** (PCB가 IR로 노출) | 사용 (HDC302x I2C / DHT11 GPIO fallback) |
| `get_chassis_stabil` (MPU6050) | **현재는 Pi 직결 — 사용** (리비전 후 PCB 이관) | 사용 |

**ADS1256 init graceful fallback 추가** — PCB 시스템에서 `import dlc_sensors` 실패 방지:

```python
try:
    sys.path.append('/home/gadgetini/.../ADS1256/python3')
    import ADS1256 as _ads_lib
    _ADC = _ads_lib.ADS1256()
    _ADC.ADS1256_init()
    _ADC_AVAILABLE = True
except Exception as e:
    print(f"ADS1256 init failed (OK if PCB present): {e}")
    _ADC = None
    _ADC_AVAILABLE = False

def get_coolant_temp(ad_index, adc_samples=None):
    if not _ADC_AVAILABLE:
        return None
    # ... 기존 로직

def poll_coolant(rd):
    if not _ADC_AVAILABLE:
        return    # PCB path에선 어차피 호출 안 됨
    # ... 기존 로직
```

env 함수들은 이미 graceful (HDC302x/DHT11/MPU6050 try/except 처리됨).

**[control_board/env_sensors.py](../control_board/env_sensors.py) 폐기**: PCB가 air_temp/humit를 센싱하므로 Pi 측 env_sensors.py는 더 이상 운용 데이터 소스가 아님. HDC302x I2C 우선 패턴은 Legacy hw 운용 시 dlc_sensors.py가 자체적으로 처리. 파일 자체는 삭제.

**Public API 정리**:

```python
# dlc_sensors.py
def get_coolant_temp(ad_index, adc_samples=None): ...
def get_coolant_leak_detection(adc_samples=None): ...
def get_coolant_level_detection(adc_samples=None): ...
def get_air_temp(): ...           # HDC302x 우선, DHT11 fallback (Legacy path 한정)
def get_air_humit(): ...
def get_chassis_stabil(): ...     # MPU6050 (현재 양 path 공통, 리비전 후 PCB 이관)

# 신규 entry 함수
def poll_coolant(rd):
    """ADS1256으로 coolant_temp_*, leak, level 일괄 read + Redis SET. Legacy hw 한정."""

def update_env(rd):
    """HDC302x/DHT11으로 air_temp, air_humit Redis SET. Legacy hw 한정."""

def update_chassis(rd):
    """MPU6050으로 chassis_stabil Redis SET. 양 path 공통 (현재 한정)."""
```

### `exporter/pcb_config.yaml` (control_board/config.yaml 이동 + 정리)

```yaml
modbus: {...}
loop:
  cycle_seconds: 1
pwm_freq: {...}

initial_pwm_duty:
  pump:
    ch1: 600          # 60% — fixed duty
    ch2: 600
    ch3: 600
    ch4: 600
  fan:
    ch7: 80           # 8% — fan_curve min과 일치 (영구 회전 baseline)
    ch8: 80
    ch9: 80
    ch10: 1000        # RPi cooling fan, always 100%

fan_cold_start:
  initial_duty: 100   # 10% — 실측 검증된 cold start 최소
  initial_seconds: 3
  # 이후 fan_curve.min_duty(=80, 8%)로 자연 ramp down

fan_curve:
  min_temp: 30        # ASHRAE W3 공급수 상한 근사 — fan_curve 시작점
  max_temp: 60
  min_duty: 80        # 8%
  max_duty: 1000

comm: {...}
pump:
  max_flow_lpm: 16
  flow_multiplier: 1.47

wiring:
  ntc: {...}                       # machine_config.py와 정보 중복 — 참조용 유지
  din: {level_bit: 1}
  ain: {leak_ch: 8, leak_threshold_v: 2}
  pulse: {fan_tach_chs: [8, 9]}
  pwm: {pump_ch: [...], fan_ch: [7, 8, 9]}
```

**v1 대비 삭제**: `standby_duty`, `gating` 섹션 전체.

**구분 기준**: "machine 모델이 바뀌면 같이 바뀌는가?" → Yes면 machine_config.py, No면 pcb_config.yaml.

### 센서 처리 — 비대칭 구조 유지 (drivers/ 폴더 불필요)

Legacy(ADS1256)와 PCB(Modbus)는 코드 양·복잡도가 다르므로 **억지 대칭 ABC 없이 자연스러운 형태**:

- **Legacy**: `dlc_sensors.py` 단일 모듈에 함수 묶음
- **PCB**: `pcb_driver.py` 단일 모듈에 클래스 (Modbus client + read + write)
- **Cooling 정책**: `pcb_control.py` 단일 파일 (FanCurveController 클래스. 상태 머신 클래스 없음)

```python
# pcb_driver.py (신규)
class PCBDriver:
    """PCB Modbus client + sensor read + actuator write."""
    def __init__(self, port, baud, slave): ...
    def poll(self, rd): ...                # coolant_*, leak, level, air_temp, air_humit, comm_status
    def apply_duty(self, pump, fan): ...   # PWM write
    def write_dout(self, bitmask): ...     # 향후 emergency stop 등

def probe_pcb() -> PCBDriver | None: ...   # 현 pcb_bootstrap.py 로직 흡수
```

```python
# pcb_control.py (PCB 전용 cooling 정책 단일 파일)
class FanCurveController:
    def __init__(self, pcb: PCBDriver, cfg: dict): ...
    def cold_start_kick(self, kick_cfg): ...      # 부팅 시 10% × 3초
    def update(self, rd): ...                      # fan_curve + pump 60% (단일 동작 — STANDBY 분기 없음)
```

**왜 ABC 불필요**: main loop의 if/else 분기 한 곳만 다름. 공통 인터페이스 강제할 만큼 코드 중복 없음. 비대칭이 가독성에 유리.

### `data_crawler.service` (기존 명칭 유지, 역할 확장)

```ini
[Unit]
Description=Gadgetini sensor collector (auto-detects PCB or legacy ADS1256).
After=redis.service
# Conflicts= 제거 (control_board/pcb_bootstrap 폐기로 mutual exclusion 불필요)

[Service]
Type=simple
WorkingDirectory=/home/gadgetini/gadgetini/src
ExecStart=/usr/bin/python3 -m exporter.data_crawler
Restart=always
RestartSec=5
User=gadgetini
Group=gadgetini
SupplementaryGroups=dialout

[Install]
WantedBy=multi-user.target
```

`pcb_bootstrap.service` + `pcb_watcher.service` + `control_board.service` 폐기.

---

## 리비전 후 변경 예상

리비전 작업 완료 시점에 추가될 변경사항. 본 통합 작업의 1차 deliverable에는 포함되지 않음.

### 하드웨어
- PCB 5VSB 입력 추가 (도메인 분리)
- MPU6050 (chassis_stabil) → PCB로 이관 (Modbus IR로 노출)

### 소프트웨어
- `dlc_sensors.update_chassis(rd)` 호출 폐기 → PCB가 IR로 노출 → `pcb.poll(rd)`이 자동 처리
- Pi가 OFF여도 PCB가 자체 안전 모니터링 (leak/level 로컬 alarm) 가능성 검토
- `comm_status` 키의 의미 확장 — PCB 살아 있는데 Pi가 막 깨어났을 때 데이터 freshness 표현

### 운용 변화
- 메인보드 ON 직후 PCB 부팅 대기 시간 제거 (이미 깨어 있음) → 모니터링 dead window 축소
- Pre-warm: 메인보드 ON 신호 받고 12V 라인 안정화될 때까지 PCB가 sensor warmup

---

## 통합 전/후 비교

### 통합 전

```
src/
├── exporter/
│   ├── data_crawler.py          ← legacy backend main loop
│   ├── dlc_sensors.py           ← ADS1256 + RPi I2C/GPIO
│   ├── machine_config.py        ← legacy 채널 매핑만
│   └── sensor_exporter.py       ← Prometheus exposition
└── control_board/
    ├── main.py / main_loop.py / pcb_bootstrap.py / pcb_watcher.py
    ├── polling.py / controller.py
    ├── env_sensors.py           ← (현재 PCB가 env 센싱하므로 미사용)
    ├── modbus_client.py / registers.py / redis_keys.py
    └── config.yaml              ← PCB wiring 포함

systemd:
├── pcb_bootstrap.service        ← oneshot, 부팅 시 PCB probe
├── pcb_watcher.service          ← runtime hot-plug detector
├── control_board.service        ← Conflicts=data_crawler
└── data_crawler.service         ← multi-user.target
```

### 통합 후

```
src/
├── exporter/                    ← ★ 단일 패키지
│   ├── data_crawler.py          ← ★ entrypoint + PCB probe + 단일 main loop
│   ├── dlc_sensors.py           ← ★ Legacy 한정 센서 (ADS1256 + I2C/GPIO + MPU6050)
│   │                              graceful fallback 추가, entry 함수 신규
│   ├── pcb_driver.py            ← ★ 신규 — PCB hw I/O 단일 파일
│   │                              polling.py + modbus_client.py + registers.py + pcb_bootstrap.py 흡수
│   │                              class PCBDriver + def probe_pcb()
│   ├── pcb_control.py           ← ★ 신규 — PCB cooling 정책 (FanCurveController만)
│   │                              controller.py 흡수. CoolingStateTracker 없음
│   ├── machine_config.py        ← ★ PCB / ADS1256 채널 매핑 두 dict
│   ├── pcb_config.yaml          ← (control_board/config.yaml 이동, standby/gating 섹션 제거)
│   ├── redis_keys.py            ← (control_board에서 이동, 통합)
│   └── sensor_exporter.py       ← (변경 없음)
└── control_board/               ← 폐기 (모든 코드 src/exporter/로 이동/흡수)

systemd:
└── data_crawler.service         ← ★ 단일 service (기존 명칭 유지)
```

| 변경 분량 | 전 | 후 |
|---|---|---|
| Service unit | 4개 | 1개 |
| Python 패키지 | 2개 | 1개 |
| Channel mapping 단일 source | 분산 | machine_config.py |
| 환경 센서 코드 | 2곳 중복 (실제로는 PCB가 센싱) | 1곳 (Legacy 한정) |
| 메인보드 의존성 | OFF → PCB OFF → 모니터링 끊김 | (리비전 전) 동일 / (리비전 후) **자율 sensing** |

---

## 의사결정 포인트 요약

### 코드 구조

| 결정 | 선택 | 근거 |
|---|---|---|
| Wiring 위치 | machine_config.py (PCB + Legacy 두 dict) | machine 변천사를 한 곳에서 관리. config.ini는 user-facing minimal 유지 |
| 채널 매핑 자료구조 | 머신별 dict 두 개 (`COOLANT_CHANNELS`, `COOLANT_CHANNELS_PCB`) | PCB와 Legacy 평행 |
| pcb_config.yaml 잔존 항목 | PCB 운용 knob + fan_curve + fan_cold_start | "PCB 있을 때만 의미 있는 값" |
| Backend probe 시점 | 부팅 시 1회 | runtime 재probe 불필요. pcb_watcher 폐기 |
| 환경 센서 코드 | dlc_sensors.py에 Legacy 한정 보존 | PCB가 env 센싱하므로 PCB path에서는 미호출 |
| Service 명 | `data_crawler.service` 유지 | systemd 호환성 |
| Entry point | `exporter/data_crawler.py` 유지 | 경로 변경 없음 |
| Package home | `src/exporter/` | control_board/ 폐기 흡수 |

### Cooling 제어 전략 (v2 — 단순화)

| 결정 | 선택 | 근거 |
|---|---|---|
| 상태 머신 | **없음** | 12V 유무가 하드웨어 인터록. firmware enable 게이팅 불필요 |
| 펌프 duty | 60% fixed (12V 살아있는 동안) | 유량 센서 없음 |
| 팬 duty | fan_curve (8~100%, outlet 30~60°C 선형) | 표준 ramp |
| Fan cold start kick | 10% × 3초 → 8% 정착 | stall 회피 (12V 인가 직후마다) |
| 30°C 임계 | **alert only** (ASHRAE W3 공급수 상한 근사) | 제어 신호 X, 모니터링 신호 O |

---

## Critical files

수정:
- [machine_config.py](machine_config.py) — `COOLANT_CHANNELS_PCB` 신규 추가, 기존 `COOLANT_CHANNELS`는 Legacy 한정으로 유지
- [data_crawler.py](data_crawler.py) — entrypoint 확장 (driver probe + 단일 main loop. **CoolingStateTracker 없음**)
- [dlc_sensors.py](dlc_sensors.py) — ADS1256 graceful fallback 추가. env 함수는 Legacy path 한정으로 의미 보존
- `../configure/daemons/gadgetini/data_crawler.service` — `[Install] WantedBy=multi-user.target` 확인

이동 (control_board → exporter):
- `../control_board/redis_keys.py` → `redis_keys.py` (기존 키와 통합)
- `../control_board/config.yaml` → `pcb_config.yaml` (`standby_duty`, `gating` 섹션 제거)
- `../control_board/modbus_client.py` + `registers.py` + `polling.py` + `pcb_bootstrap.py` → **`pcb_driver.py` 단일 파일**
- `../control_board/controller.py` → **`pcb_control.py`** 의 FanCurveController로 흡수

신규:
- `pcb_driver.py` (class PCBDriver + def probe_pcb())
- `pcb_control.py` (FanCurveController만 — 상태 머신 클래스 없음)

폐기:
- `../control_board/main.py`, `main_loop.py`, `pcb_bootstrap.py`, `pcb_watcher.py`, `env_sensors.py`
- `../control_board/` 패키지 자체
- `../configure/daemons/gadgetini/pcb_bootstrap.service`, `pcb_watcher.service`, `control_board.service`

변경 없음:
- `../display/config.ini` — user-facing minimal 유지
- [sensor_exporter.py](sensor_exporter.py) — Redis 키 unchanged

---

## Verification (실제 구현 단계에서)

### 센서 경로 분기 / 채널 매핑

1. **Legacy path (Gen1~2)**: ADS1256 hw에서 `data_crawler.service` 단일 실행 → coolant_temp_* + air_temp + air_humit Redis SET, 통합 전과 동일 값
2. **PCB path (Gen3 dg5w)**: PCB hw에서 동일 service가 PCB 경로로 자동 분기 → coolant_temp_inlet1/outlet1 + comm_status + air_temp + air_humit + leak/level 정상 SET
3. **PCB path (Gen3 dg5r)**: 4채널 coolant + 동일 env/comm_status SET
4. **PCB 시스템에서 ADS1256 미장착**:
   - `import dlc_sensors` 성공 (graceful fallback)
   - `dlc_sensors._ADC_AVAILABLE == False`
   - `poll_coolant(rd)` no-op (예외 없음)
   - `update_chassis(rd)`는 MPU6050 try/except 통과
5. **Probe fallback**: PCB 케이블 분리 후 service 재시작 → Legacy 경로로 자동 분기
6. **machine_config 검증**:
   - PCB path: `COOLANT_CHANNELS_PCB['dg5w']` → inlet1/outlet1만 SET
   - PCB path: `COOLANT_CHANNELS_PCB['dg5r']` → 4개 다 SET
   - Legacy path: `COOLANT_CHANNELS[MACHINE]`로 머신별 정상 매핑
7. **Sensor exporter 무영향**: Prometheus :9003 endpoint metric 셋이 통합 전후 동일

### Cooling (PCB path만)

8. **부팅 시 fan cold start**: 부팅 직후 3초간 fan duty = 100 → 이후 fan duty = 80 정착, tach RPM > 0
9. **정상 운용**: 펌프 duty = 600 (60%), 팬 duty = fan_curve 값 (outlet 30°C → 80, 60°C → 1000)
10. **30°C alert**: outlet > 30°C 시 Redis alert flag SET (Prometheus exposition은 별도 검토)

### NTC noise

11. **노이즈 baseline 재실측**: 단일 NTC stdev < 0.05°C, ΔT stdev < 0.1°C
12. **운용 중 NTC 개체차 systematic offset 모니터링** — 운용 데이터로 보정 필요 여부 판단 (v1에서 0.87°C 관찰됐으나 측정 오류 가능성)

---

## TODO

- [ ] backend probe 실패 시 fail-safe 동작 (PCB 응답 없음 + ADS1256도 미장착 → 어떻게 처리?)
- [ ] `pcb_config.yaml` 내 wiring.din/ain/pulse/pwm이 dg5w/dg5r마다 다를 수 있는지 확인 → 다르다면 machine_config.py로 이동 검토
- [ ] `redis_keys.py` 통합 시 키 상수 충돌·누락 확인 (COMM_STATUS, PWM_DUTY_* owner 명확화)
- [ ] 30°C alert를 Prometheus metric으로 노출할지 결정 (Grafana 대시보드)
- [ ] Fan cold start kick 자동 재시도 — 부팅 외에 fan_rpm이 0으로 떨어지면 (먼지/일시 dip) cold start 재실행
- [ ] 마이그레이션 단계별 PR plan 작성 (회귀 위험 분산)
- [ ] 통합 전 in-flight production 영향도 평가 (특히 dg5r Gen3 운용 중인 머신)
- [ ] 통합 후 control_board/ 폐기 시점 — archive vs delete
- [ ] 리비전 후 작업 별도 design 문서로 분리 (`POST_REVISION_DESIGN.md` 가칭)
