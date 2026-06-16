# Collector 통합 설계 — pcb_bootstrap + control_board → data_crawler 단일화

> **Status**: Design v3 — Rev_C 현실 반영 (env는 Pi-side 상시 센싱, PCB liveness는 1Hz health check, 5VSB는 차기 보드 Rev_D).
> v1의 자율 냉각 상태 머신은 폐기 — 사유는 [§ 전원 아키텍처 결정](#전원-아키텍처-결정-v1--v2) 참조.
> v2 대비 정정: ① 온/습도는 PCB가 아니라 Pi 직결 센서 소스(양 경로 공통, 메인보드 전원 무관) ② 백엔드 선택은 부팅 1회 probe가 아니라 ADS1256 존재 여부 + 1Hz health check (Rev_C는 메인보드 전원에 따라 PCB가 cycling).
>
> **보드 리비전 표기**: 현재 보드 = **Rev_C** (5VSB 없음, 메인보드 12V 단일 전원). 차기 보드 = **Rev_D** (5VSB 도입 예정). 코드 [registers.py](registers.py) 주석의 "Rev2"는 보드 매뉴얼 §4 참조용이며 본 문서의 Rev_C/Rev_D 표기와는 별개.

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

### v2 결정 (차기 보드 Rev_D 방향 — 아직 미적용)

> ⚠️ 아래 5VSB 구조는 **차기 보드 Rev_D 목표**다. **현재 보드 Rev_C는 5VSB를 공급하지 않으며**, PCB는 메인보드 12V 단일 전원으로만 동작한다 (메인보드 OFF → PCB OFF). 본 통합 작업의 1차 타깃은 Rev_C이며, 5VSB 관련 동작은 Rev_D 도입 후에야 유효하다. → [§ 현재 하드웨어 스펙 (Rev_C)](#현재리비전-전-하드웨어-스펙) 참조.

**제어보드 리비전(Rev_D)으로 5V 상시 + 12V 스위치드 분리 전원 도입** (ATX 패턴):

| 도메인 | 공급원 | 항상 ON | 용도 |
|---|---|---|---|
| **5VSB** (Rev_D) | 별도 standby 라인 | ✓ | PCB MCU + 모든 센서 |
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

## 현재(리비전 전) 하드웨어 스펙 (Rev_C)

본 통합 작업이 1차로 타겟하는 상태 — Rev_D 리비전 적용 전:

- **PCB 전원**: 메인보드 12V 단일 입력 (메인보드 OFF → PCB OFF). **5VSB 없음.** 메인보드는 부팅 시 전원을 3~4회 cycling → PCB도 그에 따라 켜졌다 꺼짐.
- **PCB 센서 범위**: NTC × N (coolant), leak, level, flow. **air_temp/air_humit는 PCB가 센싱하지 않음** (PCB Modbus 레지스터 맵에 공기 온/습도 레지스터 없음, NTC 냉각수 CH13~16만 존재).
- **Pi 직결 센서 (상시 — 메인보드 전원 무관)**: HDC302x/DHT11 (air_temp/air_humit), MPU6050 (dg5w 한정 chassis_stabil), ADS1256 (Gen1~2 legacy 한정 coolant).
- **데이터 경로**: PCB → Modbus → Pi (Redis) [메인보드 ON시] / Pi 직결 센서 → Redis [상시]
- **상시 센싱**: **온/습도만** 항상 가능 (Pi 직결). 나머지 PCB 센싱(coolant/leak/level/flow)은 메인보드 ON 일 때만.
- **Cooling**: 메인보드 ON(=12V 인가) 시점부터 펌프 fixed duty + fan_curve. STANDBY 개념 없음 (12V 자체가 없음 = 하드웨어 인터록).

→ 본 통합 작업은 Rev_C·Rev_D 모두에서 동작. Rev_D 이후 추가 변경은 [§ Rev_D 변경 예상](#리비전-후-변경-예상) 참조.

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
import pcb_driver
import pcb_control

def main():
    rd = redis.StrictRedis(..., decode_responses=True)

    # 1. 백엔드 family = ADS1256 존재 여부 (전원 무관·결정적). 부팅 1회 Modbus probe 아님.
    backend = pcb_driver.detect_backend()    # 'pcb' | 'legacy'

    driver = reloader = None
    if backend == 'pcb':
        cfg = load_pcb_config()
        driver = pcb_driver.PCBDriver(cfg)
        reloader = pcb_control.ConfigReloader(PCB_CONFIG_PATH, cfg)

    while True:
        if backend == 'pcb':
            controller = reloader.maybe_reload(driver)   # config.yaml 핫리로드
            if driver.health_check():                    # 1Hz 경량 health check
                if down→up: driver.on_connect(rd)        # initial state 재적용 (PCB 전원 복귀)
                if driver.poll(rd):                      # Modbus → coolant_*, leak, level, flow, comm_status
                    controller.update(driver, rd)        # fan_curve + pump fixed
            # health check 실패(메인보드 OFF/cycling): 풀 poll 생략, comm_status만 갱신
        else:
            dlc_sensors.poll_coolant(rd)                 # ADS1256 → coolant_*, leak, level (legacy)

        # env / chassis — 양 백엔드 공통, 무조건 (Pi 직결 상시 센싱)
        dlc_sensors.update_env(rd)       # HDC302x/DHT11 → air_temp, air_humit
        dlc_sensors.update_chassis(rd)   # MPU6050 → chassis_stabil (dg5w 한정)

        sleep(cycle_s)

if __name__ == '__main__':
    main()
```

**핵심 (Rev_C)**: PCB health check가 실패해도(메인보드 OFF) `update_env`/`update_chassis`는 계속 실행 → **온/습도 상시 보장**. PCB가 air_temp/humit를 센싱한다는 v2 가정은 폐기 (PCB 레지스터에 해당 센서 없음).

**v1 대비 단순화**:
- `CoolingStateTracker` 폐기 (상태 머신 자체가 없음)
- `controller.standby(rd)` 분기 없음 — 항상 단일 명령 경로
- `cooling_state` Redis 키 폐기 (필요 시 단순 `'on' | 'off'`로 축소, 12V tach 살아있으면 'on')

**왜 백엔드를 ADS1256 존재로 판별?**:
- Rev_C는 PCB 전원이 메인보드에 종속 → 부팅 시 PCB가 꺼져 있을 수 있어 **Modbus 1회 probe로는 legacy/PCB 구분 불가** (무응답이 "legacy 머신"인지 "메인보드 OFF"인지 모호).
- ADS1256은 Pi SPI 보드라 메인보드 전원과 무관·결정적 → 장착=legacy, 미장착=PCB로 명확.
- PCB liveness(켜짐/꺼짐)는 별도로 매 cycle `health_check()`로 추적 (단일 레지스터 read, short timeout, no-retry → PCB OFF여도 cycle이 막히지 않아 env 상시 센싱 보존).

**컴포넌트 존재 조건**:

| 컴포넌트 | 항상 존재 | PCB일 때만 |
|---|---|---|
| `driver` (PCBDriver 또는 ADS1256Driver) | ✓ | — |
| `cfg` (pcb_config.yaml dict) | — | ✓ |
| `controller` (FanCurveController) | — | ✓ |

> NoOp 패턴 안 씀 — `controller is None` 직접 비교가 더 명료.

**백엔드 판별 + liveness** (현 [../control_board/pcb_bootstrap.py](../control_board/pcb_bootstrap.py) + `pcb_watcher.py` 로직을 main loop로 흡수):

```
family 선택 (1회):  detect_backend()
    ADS1256 init 성공 → 'legacy'   (Gen1~2)
    ADS1256 미장착   → 'pcb'       (Gen3 제어보드)

PCB liveness (매 cycle, PCB 머신 한정):  PCBDriver.health_check()
    단일 read_input_registers(0, 1), short timeout(~0.3s), retries=0
    baud/port 미확정이면 후보 순회로 lock, 확정 후엔 단일 read
        ├─ 응답 있음 → 살아있음 → 풀 poll + controller
        └─ 응답 없음 → 메인보드 OFF/cycling → 풀 poll skip, comm_status 갱신
```

> ⚠️ **부팅 1회 probe 아님** (v2 정정). Rev_C는 PCB 전원이 메인보드에 종속되고 메인보드가 부팅 시 3~4회 cycling하므로, 1회 probe는 PCB가 막 꺼진 순간에 실패해 legacy로 오폴백된다 (실측 사례). 따라서 **family는 ADS1256 존재로**(전원 무관), **liveness는 매 cycle health check로** 판별한다. 별도 `pcb_watcher.service`는 여전히 불필요 — health check가 main loop 안에 있기 때문. `/dev/serial0`(Pi UART)은 PCB 전원과 무관하게 상존하므로 포트 재open도 불필요. 일시/지속 통신 끊김은 `comm_status` Redis 키로 추적.

### Cooling control (v2 — 단순화)

**상태 머신 없음**. PCB가 살아 있는 동안에는 항상 동일 명령 송신:

| 항목 | 값 | 근거 |
|---|---|---|
| 펌프 duty | 60% fixed (ch1~4 = 600) | 유량 센서 없음 → fixed-duty 운용 정책 |
| 팬 duty | fan_curve (8~100%) | outlet 25°C → 8%, 60°C → 100% 선형 |
| 30°C alert 임계 | ASHRAE W3 공급수 상한 근사 | **alert only** — 제어 아닌 모니터링 |

> fan cold start kick(10%×3초)은 **미적용** — 초기 fan duty를 곧바로 fan_curve min(8%)으로 두고, 12V 인가(메인보드 ON) 직후 fan_curve가 동작. (현 운용 stall 이슈 없어 단순화.)

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
3. **Cold start** — 별도 kick 없이 초기 duty를 fan_curve min(8%)으로 두고 12V 인가 직후 fan_curve 동작. 현 운용에서 stall 이슈 없음. (참고: 과거 실측에서 10% × 3초 kick이 stall 회피 최소였으나, 8% 상시 적용으로 충분히 회피되어 미적용.)

### `exporter/dlc_sensors.py` — coolant는 legacy 전용, env/chassis는 양 경로 공통

**Coolant(ADS1256) 함수만 legacy 한정**이고, **env(air_temp/humit)·chassis(MPU6050)는 Pi 직결이라 양 백엔드 공통**으로 쓰인다. PCB는 공기 온/습도를 센싱하지 않으므로(레지스터 없음), PCB 경로에서도 온/습도는 반드시 dlc_sensors의 env 함수로 수집해야 한다.

| 함수 | PCB path | Legacy path |
|---|---|---|
| `get_coolant_temp` | 사용 안 함 (PCB Modbus가 NTC 노출) | 사용 (ADS1256) |
| `get_coolant_leak/level_detection` | 사용 안 함 (PCB가 DIN/AIN으로) | 사용 (ADS1256) |
| `get_air_temp` / `get_air_humit` | **사용** (Pi-side, 상시) | 사용 (Pi-side, 상시) |
| `get_chassis_stabil` (MPU6050) | **사용** (Pi 직결, Rev_D에서 PCB 이관) | 사용 |

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

**[control_board/env_sensors.py](../control_board/env_sensors.py) 폐기**: PCB가 센싱해서가 아니라, **env 로직을 dlc_sensors.py 한 곳으로 통합**하기 때문. env_sensors.py는 dlc_sensors.py와 거의 동일한 HDC302x/DHT11/MPU6050 코드의 중복본이므로, 더 견고한 구현(numpy 선택적, 실패 시 None 반환)을 dlc_sensors.py로 흡수하고 양 경로 공통으로 호출 → 중복 파일 삭제. **온/습도 수집 코드는 사라지지 않고 dlc_sensors.py로 일원화**된다.

**Public API 정리**:

```python
# dlc_sensors.py
def get_coolant_temp(ad_index, adc_samples=None): ...
def get_coolant_leak_detection(adc_samples=None): ...
def get_coolant_level_detection(adc_samples=None): ...
def get_air_temp(): ...           # HDC302x 우선, DHT11 fallback (양 path 공통, Pi-side 상시)
def get_air_humit(): ...
def get_chassis_stabil(): ...     # MPU6050 (양 path 공통, dg5w 한정, Rev_D에서 PCB 이관)

# 신규 entry 함수
def poll_coolant(rd):
    """ADS1256으로 coolant_temp_*, leak, level 일괄 read + Redis SET. Legacy hw 한정."""

def update_env(rd):
    """HDC302x/DHT11으로 air_temp, air_humit Redis SET. 양 백엔드 공통 (Pi-side 상시)."""

def update_chassis(rd):
    """MPU6050으로 chassis_stabil Redis SET. 양 path 공통 (dg5w 한정, Rev_D에서 PCB 이관)."""
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

fan_curve:
  min_temp: 25        # fan_curve 시작점 (현 운용값 유지)
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
    def __init__(self, cfg): ...
    def health_check(self) -> bool: ...    # 단일 레지스터 read (liveness, baud/port lock)
    def poll(self, rd): ...                # coolant_*, leak, level, flow, fan_rpm, pwm_duty (env 미포함)
    def on_connect(self, rd): ...          # down→up 시 initial state 재적용
    def write_register/registers(...): ... # PWM write

def detect_backend() -> str: ...           # 'pcb' | 'legacy' — ADS1256 존재 여부
```

```python
# pcb_control.py (PCB 전용 cooling 정책 단일 파일)
class FanCurveController:
    def __init__(self, fan_curve_cfg, fan_pwm_chs): ...
    def update(self, pcb, rd): ...                 # fan_curve (단일 동작 — STANDBY/cold-start 분기 없음)

# + ConfigReloader (pcb_config.yaml mtime watch → 핫리로드)
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

## Rev_D 변경 예상 (5VSB 도입 후)

차기 보드 Rev_D(5VSB 상시 전원) 작업 완료 시점에 추가될 변경사항. 본 통합 작업의 1차 deliverable(Rev_C)에는 포함되지 않음.

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
│   │                              class PCBDriver(health_check/poll) + def detect_backend()
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
| 메인보드 의존성 | OFF → PCB OFF → coolant 끊김 (온/습도는 Pi 직결 상시) | (Rev_C) 동일 / (Rev_D) **PCB 자율 sensing** |

---

## 의사결정 포인트 요약

### 코드 구조

| 결정 | 선택 | 근거 |
|---|---|---|
| Wiring 위치 | machine_config.py (PCB + Legacy 두 dict) | machine 변천사를 한 곳에서 관리. config.ini는 user-facing minimal 유지 |
| 채널 매핑 자료구조 | 머신별 dict 두 개 (`COOLANT_CHANNELS`, `COOLANT_CHANNELS_PCB`) | PCB와 Legacy 평행 |
| pcb_config.yaml 잔존 항목 | PCB 운용 knob + fan_curve | "PCB 있을 때만 의미 있는 값" |
| Backend family 판별 | ADS1256 존재 여부 | 전원 무관·결정적. Modbus 1회 probe는 Rev_C cycling에 부적합 |
| PCB liveness | 매 cycle 1Hz health check | 메인보드 전원 cycling 추적. 별도 pcb_watcher 프로세스 불필요 |
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
| Fan cold start kick | **미적용** (초기 duty = fan_curve min 8%) | 8% 상시로 stall 충분 회피 |
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
- `pcb_driver.py` (class PCBDriver(health_check/poll/on_connect) + def detect_backend())
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

8. **부팅/PCB 전원 복귀 시 initial state**: health check 통과(down→up) 직후 펌프 duty=600, 팬 초기 duty=80, tach RPM > 0
9. **정상 운용**: 펌프 duty = 600 (60%), 팬 duty = fan_curve 값 (outlet 25°C → 80, 60°C → 1000)
10. **30°C alert**: outlet > 30°C 시 Redis alert flag SET (Prometheus exposition은 별도 검토)

### NTC noise

11. **노이즈 baseline 재실측**: 단일 NTC stdev < 0.05°C, ΔT stdev < 0.1°C
12. **운용 중 NTC 개체차 systematic offset 모니터링** — 운용 데이터로 보정 필요 여부 판단 (v1에서 0.87°C 관찰됐으나 측정 오류 가능성)

---

## TODO

- [ ] ADS1256 미장착 + PCB도 영영 무응답(오배선/오설정) 시 운용자 알림 방법 (현재는 PCB 머신으로 간주하고 env만 SET + comm_status=disconnected)
- [ ] `pcb_config.yaml` 내 wiring.din/ain/pulse/pwm이 dg5w/dg5r마다 다를 수 있는지 확인 → 다르다면 machine_config.py로 이동 검토
- [ ] 30°C alert를 Prometheus metric으로 노출할지 결정 (Grafana 대시보드)
- [ ] Rev_D 작업 별도 design 문서로 분리 (`REV_D_DESIGN.md` 가칭)
