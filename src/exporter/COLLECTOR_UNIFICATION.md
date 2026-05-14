# Collector 통합 설계 — pcb_bootstrap + control_board → data_crawler 단일화

> **Status**: Design draft (개선 필요). 이 문서는 향후 작업 시작점이며, 구현 전에 추가 검토·갱신 필요.

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
- RPi-직결 센서 코드가 두 곳에 중복 ([dlc_sensors.py](dlc_sensors.py)의 air_temp/humit/chassis_stabil 로직과 [../control_board/env_sensors.py](../control_board/env_sensors.py)가 거의 동일 — 단, control_board 쪽이 HDC302x I2C 지원 추가됨)
- 채널 매핑이 두 곳에 분산: legacy는 [machine_config.py:13-16](machine_config.py#L13-L16), PCB는 [../control_board/config.yaml의 wiring 섹션](../control_board/config.yaml#L46-L70)
- 신 sub-variant 추가 시 두 코드베이스 다 수정해야 함
- **PCB 전원이 메인보드 의존 → 서버 OFF 시 모니터링 끊김** (향후 PDB 12V 독립 전원으로 전환 예정)

**목표**: 단일 collector 코드 (`data_crawler.py`) + 단일 service (`data_crawler.service`). 모든 변형(machine type × backend × wiring)을 **machine_config.py 한 곳**에서 선언. config.ini는 사용자 향(machine 식별 + 카운트만), 사용자는 변천사 모름. PDB 12V 독립 전원으로 전환 시 **자율 냉각 제어** (메인보드 신호 의존 X, 냉각수 온도 기반).

---

## 통합 후 책임 분담 (Where each thing lives)

### `display/config.ini` (사용자가 편집, web UI 연동)

**역할 변화 없음** — minimal user-facing config. 사용자가 "이 머신은 dg5r에 GPU 8개, CPU 2개"만 선언.

```ini
[PRODUCT]
name=dg5r              # 'dg5w' | 'dg5r'
gpu_count=8
cpu_count=2
fan_count=2
...
```

**원칙**: Wiring/채널/backend 같은 hw 변천사 정보는 **여기 절대 추가하지 않음**.

### `exporter/machine_config.py` — 두 backend 모두 머신별 매핑

**구조**: PCB와 Legacy가 동일한 패턴(`{머신: {logical: 채널}}`)을 가지는 두 개의 평행 dict. 머신별로 그 backend가 사용하는 채널을 직접 선언.

```python
# 기존 (변경 없음)
MACHINE = _cfg.get('PRODUCT', 'name', fallback='unknown').lower()
GPU_COUNT = _cfg.getint('PRODUCT', 'gpu_count', fallback=8)
CPU_COUNT = _cfg.getint('PRODUCT', 'cpu_count', fallback=2)

# Legacy ADS1256 채널 매핑 (현 상태 그대로 유지)
COOLANT_CHANNELS = {
    'dg5w': {'inlet1': 4, 'outlet1': 5},
    'dg5r': {'inlet1': 2, 'outlet1': 3, 'outlet2': 4, 'inlet2': 5},
}

# PCB Modbus NTC 채널 매핑 (신규 — 동일 패턴)
COOLANT_CHANNELS_PCB = {
    'dg5w': {'inlet1': 13, 'outlet1': 14},
    'dg5r': {'inlet1': 13, 'outlet1': 14, 'outlet2': 15, 'inlet2': 16},
}
```

**원칙**:
- **config.ini의 machine 타입(`name=dg5r`)이 진실의 source.** machine_config가 그 머신에 결선된 채널을 dict로 선언.
- **data_crawler.py는 선언된 채널을 read하고 Redis SET.** "결선됐는지 아닌지" 검사 없음 — dict 선언이 곧 그 머신의 wiring 명세.
- 새 (machine, backend) 조합 등장 시 dict에 한 줄 추가.

**Sensor failure 시 동작 (별개 robustness)**:
- 통합과 무관하게 기존 코드에 이미 있는 안전망: PCB가 `-999` sentinel 반환 또는 ADS 전압 범위 밖이면 `pipe.delete(key)`. 사용자/필드에서 케이블 분리 같은 일시 장애 시 stale 값 방지용.
- 이 동작은 "sub-variant 자동 감지" 메커니즘이 아니라 단순 sensor failure handling. 통합 후에도 그대로 유지.

### `exporter/data_crawler.py` — 단일 entrypoint, 확장

기존 단일 파일 [data_crawler.py](data_crawler.py) (~55 lines)를 다음 구조로 확장:

```python
# data_crawler.py (확장된 entrypoint)
import dlc_sensors
from pcb_driver import probe_pcb           # None or PCBDriver instance 반환
from pcb_control import FanCurveController, CoolingStateTracker

def main():
    rd = redis.StrictRedis(...)

    # 1. PCB probe FIRST — cfg 의존성 없음, 하드코딩 default 순회
    #    Boot 시 1회만 (장착된 PCB는 빠지지 않음)
    pcb = probe_pcb()                            # PCBDriver 또는 None
    log.info("PCB detected" if pcb else "no PCB — legacy ADS1256 path")

    # 2. PCB일 때만 운용 config + cooling 컴포넌트
    #    Legacy hw는 PWM/fan_curve/gating 모두 무의미
    cfg = None
    controller = None
    cooling_state = None

    if pcb is not None:
        cfg = load_pcb_config()                  # ← PCB일 때만 pcb_config.yaml 로드
        controller = FanCurveController(pcb, cfg)
        cooling_state = CoolingStateTracker(cfg['gating'])
        controller.cold_start_kick(cfg['fan_cold_start'])

    cycle_s = cfg['loop']['cycle_seconds'] if cfg else 1.0

    while True:
        # Coolant 센서 read — PCB면 Modbus, 없으면 ADS1256
        if pcb is not None:
            pcb.poll(rd)                         # Modbus → coolant_*, leak, level, comm_status
        else:
            dlc_sensors.poll_coolant(rd)         # ADS1256 → coolant_*, leak, level

        # Env 센서 (양 경로 공통 — RPi 직결 I2C/GPIO/MPU6050)
        dlc_sensors.update_env(rd)               # air_temp, air_humit, chassis_stabil

        # Cooling state + actuator (PCB 전용)
        if controller is not None:
            state = cooling_state.update(rd)
            rd.set('cooling_state', state)       # 'standby' | 'active'

            if state == 'active':
                controller.update(rd)            # fan_curve + 펌프 60%
            else:
                controller.standby(rd)           # 펌프 10%, 팬 8%

        sleep(cycle_s)

if __name__ == '__main__':
    main()
```

**왜 driver probe가 cfg 로드보다 먼저?**:
- Legacy hw (ADS1256)에서는 pcb_config.yaml 내용 **거의 전부가 무의미** — PWM duty, fan_curve, gating 임계 다 PCB 액추에이터 전용
- driver 결정 전 cfg 로드는 낭비 + 의미 혼란 (cfg를 누가 쓰는지 불명확해짐)
- Probe 자체는 하드코딩 default (port/baud)로 충분 — 현 [pcb_bootstrap.py:15-17](../control_board/pcb_bootstrap.py#L15-L17) 패턴 그대로

**컴포넌트 존재 조건 정리**:

| 컴포넌트 | 항상 존재 | PCB일 때만 |
|---|---|---|
| `driver` (PCBDriver 또는 ADS1256Driver) | ✓ | — |
| `cfg` (pcb_config.yaml dict) | — | ✓ |
| `controller` (FanCurveController) | — | ✓ |
| `cooling_state` (CoolingStateTracker) | — | ✓ (actuator 없으면 state machine 무의미) |

> NoOp 패턴 안 씀 — `controller is None` 직접 비교가 더 명료. Legacy hw path는 단순 "센서 read + Redis SET + sleep" — 최소 의존성.

**`probe_and_select_driver()` 동작 — PCB 장착 여부 자동 감지** (현 [../control_board/pcb_bootstrap.py](../control_board/pcb_bootstrap.py) 로직 흡수):

```
1. /dev/serial0 (RPi UART, RS485 직결) + /dev/ttyUSB0 (USB-RS485 어댑터) 에
   각각 baud 115200, 9600 순회로 Modbus FC04 read_input_registers(0, 1) 시도
        │
        ├─ 어떤 조합에서 응답 있음
        │     → PCB 장착 확정
        │     → return PCBDriver(coolant_channels=COOLANT_CHANNELS_PCB[MACHINE])
        │       (Modbus RTU로 NTC/leak/level read + 펌프/팬 PWM write 메서드 가능)
        │
        └─ 모두 응답 없음
              → 구hw 추정 (PCB 미장착)
              → return ADS1256Driver(coolant_channels=COOLANT_CHANNELS[MACHINE])
                (SPI로 raw voltage read → Steinhart-Hart 환산. read-only)
```

**핵심 차이점**:

| 구분 | PCBDriver | ADS1256Driver |
|---|---|---|
| 센서 read 방식 | Modbus RTU (PCB 펌웨어가 NTC→온도 환산해서 IR 28~31에 노출) | SPI (raw voltage read 후 호스트 코드에서 Steinhart-Hart 환산) |
| Sensor 키 | coolant_temp_*, coolant_leak, coolant_level, comm_status | coolant_temp_*, coolant_leak, coolant_level (comm_status 없음) |
| 액추에이터 메서드 | ✓ `apply_duty(pump, fan)` 등 PWM write 메서드 보유 | ✗ ADC 입력 전용 — write 메서드 없음 |
| Controller 연결 | `FanCurveController(driver, cfg)` 으로 묶음 | controller = None (생성 안 함) |
| 사용 머신 세대 | Gen3 (dg5w/dg5r with PCB) | Gen1~2 (PCB 미장착) |

**Probe는 부팅 시 1회만**. 장착된 PCB는 빠지지 않으므로 runtime 재probe (구 `pcb_watcher.service` 역할) 불필요. 만약 일시 통신 끊김이 발생하면 그건 cooling state machine과 별개로 `comm_status` Redis 키에서 추적.

### Cooling state machine — 냉각수 온도 기반 자율 제어 (신규)

**배경**: 향후 **PDB 12V 독립 전원**으로 전환 시 PCB가 항상 켜짐 → 메인보드 OFF여도 액추에이터에 전력 인가 가능. 메인보드 동작 신호 (host_ttl USB gadget)는 19pin 호환성 문제로 머신별 fail. **냉각수 온도만으로 자율 판단**해야 함.

**감지 신호 (2가지 OR — 어느 하나라도 만족 시 ACTIVE)**:

| 신호 | 임계 | 근거 |
|---|---|---|
| Outlet 절대 온도 | **30°C 이상** | ASHRAE W3 facility supply water 상한 근사 (STANDBY에선 outlet≈inlet이므로 공급수 30°C 도달과 동치) |
| ΔT (30s median) | **1°C 이상** | STANDBY 저-duty 펌프 (10%) 덕분에 200W 이상 모든 부하 catch |

**상태 머신 (STANDBY / ACTIVE 2상태)**:

```
[STANDBY]                              [ACTIVE]
- 펌프 10% (NTC 순환)                  - 펌프 60% (config 기본 duty)
- 팬 8%   (영구 회전, 무음)            - 팬 fan_curve (8~100%)
       │                                       ▲
       │ outlet > 30 OR ΔT > 1                 │
       │ (즉시)                                │
       └───────────────────────────────────────┤
                                                │
       ┌───────────────────────────────────────┘
       │ outlet < 27°C AND ΔT_corrected < 0.3°C
       │ AND 30분 연속 유지
       │ AND ACTIVE 진입 후 최소 30분 경과
       ▼
[STANDBY]
```

**Asymmetric hysteresis — ACTIVE 진입 쉽게, STANDBY 복귀 매우 어렵게**:

| 임계 | 값 | 근거 |
|---|---|---|
| ACTIVE 진입 outlet | 30°C | ASHRAE W3 공급수 상한 근사 (STANDBY outlet≈inlet) |
| ACTIVE 진입 ΔT | 1°C | 약 200W 이상 모든 부하 catch |
| STANDBY 복귀 outlet | 27°C (3°C hysteresis) | 산업 평균 hysteresis 3~5°C |
| STANDBY 복귀 ΔT | 0.3°C | 노이즈 floor 0.045°C × 6배 마진 |
| Grace period (STANDBY 복귀 전 stable 유지) | 30분 | CDU 표준 15~60분 |
| Minimum hold time (ACTIVE 진입 후) | 30분 | chattering 방지 |

→ 결과: 펌프 duty 변경은 **하루 보통 0~2회**. 와리가리 없음. 운용 검증 후 3°C/15분으로 완화 검토 가능.

**산업 표준 대조**: 태양열 DTC, 데이터센터 CDU (CoolIT/Asetek/Vertiv), HVAC chilled water plant 모두 동일 패턴 사용 — 검증된 아키텍처.

**센서 수집은 상태 무관 항상 동작**. PCB가 독립 전원이라 STANDBY에서도 NTC/leak/level 등 read 계속 → Redis SET. UI/Grafana에서 cooldown 후 안정 온도 관찰 가능.

**`comm_status`와 별개 키**: PCB-호스트 통신 상태(`comm_status`)는 Modbus 통신 자체의 ok/timeout/disconnected만 의미. `cooling_state`는 의미적 상태 — 두 키 분리 유지.

### NTC noise baseline (참고)

ΔT 임계값 결정 근거. 보정 없이 raw `outlet - inlet` 값을 그대로 사용.

**실측 노이즈**:
- 단일 NTC stdev: 0.025~0.041°C
- ΔT stdev: 0.045°C
- → 임계 1°C는 노이즈 floor 22배 위, 0.3°C도 6배 위로 충분한 마진

**NTC 개체차로 인한 systematic offset 가능성** (실측 결과 0.87°C 정도 관찰됐으나 측정 오류 가능성 + 영향 미미로 보정 코드 미적용):
- ACTIVE 진입 임계 1°C에 약간의 false-positive 여지 → STANDBY가 ACTIVE로 잘못 전이될 수 있음
- 운용 검증 후 실제 문제되면 그때 보정 로직 추가
- 일단 raw ΔT로 진행

### STANDBY fan 8% 근거 (참고)

왜 0%(정지) 아닌 **영구 회전 8%** 인가:

1. **Cold start stall 회피** — 4-pin PWM 팬은 정지 후 재시동 시 베어링 정지마찰 + PWM low duty 토크 부족으로 stall(미회전) 또는 시동 잡음 발생. 한 번이라도 멈추면 다음 ACTIVE 진입 때 fan_curve가 8% 명령을 내려도 안 돌 위험. 영구 회전이면 항상 회전 관성 유지 → stall 원천 차단.
2. **무음 수준** — 8% duty ≈ 1500 RPM, ≈25 dBA. 정숙한 사무실(30~35 dBA)보다 조용해 사실상 무음 인지. 사용자 입장에선 "꺼진 것과 동일".
3. **STANDBY ↔ ACTIVE 매끈한 전이** — `fan_curve.min_duty`도 동일한 8%(=80)로 맞춰 둠 ([line 463](src/exporter/COLLECTOR_UNIFICATION.md#L463)). STANDBY baseline과 ACTIVE 시작점이 같아 전이 순간 duty jump 없음 → 청각적 변화 없음.
4. **Cold start kick 실측** — 부팅 직후 stall 회피를 위해 10% × 3초 kick 후 8%로 정착 ([line 442~446](src/exporter/COLLECTOR_UNIFICATION.md#L442-L446)). 10%가 실측 검증된 cold start 최소 duty. 한 번 회전 시작하면 8%로도 회전 유지 가능 (kinetic friction < static friction).

→ 펌프 10%(NTC 신호 amplify)와 팬 8%(stall 회피 + 무음)는 각자 다른 이유로 "0% 아닌 최소값"을 채택. 둘 다 STANDBY에서 액추에이터 완전 정지를 피해 다음 전이를 부드럽게 만들기 위함.

### 센서 처리 — 비대칭 구조 (drivers/ 폴더 불필요)

ADS1256(Legacy)과 PCB(Modbus)는 코드 양·복잡도가 다르므로 **억지 대칭 ABC 없이 자연스러운 형태**로:

- **Legacy (ADS1256)**: `dlc_sensors.py` 단일 모듈에 함수 묶음. 이미 ADS1256 init + read + Steinhart-Hart 환산까지 다 들어있음 ([dlc_sensors.py:4-13, 58-59, 104-129](dlc_sensors.py))
- **PCB**: `pcb_driver.py` 단일 모듈에 클래스 (Modbus client state + read + write 메서드)

```python
# dlc_sensors.py (현재 그대로 + entry 함수 2개 추가)
# 기존 함수 — 변경 없음
def get_coolant_temp(ad_index, adc_samples=None): ...
def get_coolant_leak_detection(adc_samples=None): ...
def get_coolant_level_detection(adc_samples=None): ...
def get_air_temp(): ...
def get_air_humit(): ...
def get_chassis_stabil(): ...

# 신규 — Legacy path entry
def poll_coolant(rd):
    """ADS1256으로 coolant_temp_*, leak, level 일괄 read + Redis SET.
    현 data_crawler.py:16-53의 loop body 함수화."""
    ...

# 신규 — 양 driver path 공통 entry
def update_env(rd):
    """RPi 직결 env 센서 (HDC302x/DHT11/MPU6050) Redis SET."""
    ...
```

```python
# pcb_driver.py (신규)
class PCBDriver:
    """PCB Modbus client + sensor read + actuator write."""
    def __init__(self, port, baud, slave): ...
    def poll(self, rd): ...               # Modbus read → coolant_*, leak, level, comm_status
    def apply_duty(self, pump, fan): ...   # PWM write
    def write_dout(self, bitmask): ...     # 향후 emergency stop 등

def probe_pcb() -> PCBDriver | None:
    """부팅 시 PCB 감지. 응답 있으면 PCBDriver instance, 없으면 None.
    현 pcb_bootstrap.py 로직 흡수."""
    PORTS = ['/dev/serial0', '/dev/ttyUSB0']
    BAUDS = [115200, 9600]
    for port in PORTS:
        for baud in BAUDS:
            try:
                d = PCBDriver(port, baud, slave=1)
                if d.probe():
                    return d
            except Exception:
                pass
    return None
```

**왜 ABC가 불필요한가**: Legacy path는 `dlc_sensors.poll_coolant(rd)` 함수 1줄 호출, PCB path는 `pcb.poll(rd)` 메서드 1줄 호출 — main loop에서 if/else 분기 한 곳만 다름. 공통 인터페이스 강제할 만큼 코드 중복 없음. 비대칭이 오히려 가독성 좋음.

**Cooling 정책은 별도 단일 모듈** (`exporter/pcb_control.py`) — PCB 전용 명시:

```python
# pcb_control.py (PCB 전용 cooling 정책 단일 파일)

class FanCurveController:
    def __init__(self, pcb: PCBDriver, cfg: dict): ...
    def cold_start_kick(self, kick_cfg): ...      # 부팅 시 10% × 3초
    def update(self, rd): ...                      # ACTIVE — fan_curve + pump 60%
    def standby(self, rd): ...                     # STANDBY — pump 10%, fan 8%

class CoolingStateTracker:
    def __init__(self, gating_cfg: dict): ...
    def update(self, rd) -> str: ...   # 'standby' | 'active' (raw ΔT 사용, 보정 없음)
```

두 클래스가 강하게 결합 (state_tracker 결과 → fan_curve 동작 결정)이라 단일 파일로 묶음. 약 180줄 예상.

→ PCB Driver(hw I/O)와 pcb_control(cooling policy)는 분리된 관심사. PCB일 때만 둘이 묶여 운용. Legacy는 둘 다 없음.

### `exporter/dlc_sensors.py` — RPi 직결 센서의 단일 source (확장 유지)

**원칙**: PCB가 hw적으로 접근할 수 없는 모든 센서는 **dlc_sensors.py 단일 모듈**에서 처리. driver 종류와 무관.

- **ADS1256 SPI**: coolant_temp_*, coolant_leak, coolant_level (Legacy hw에서만 의미 있음)
- **I2C/GPIO 환경 센서**: air_temp, air_humit (HDC302x I2C 우선, DHT11 GPIO fallback) — **양 hw 모두 RPi에서 직접 read 필요** (PCB로 라우팅 불가)
- **MPU6050**: chassis_stabil (dg5w 한정)

**[control_board/env_sensors.py](../control_board/env_sensors.py) 폐기 + 개선분 흡수**:

현재 dlc_sensors.py는 이미 HDC302x I2C 우선 + DHT11 fallback 패턴이 있음 ([line 16-44](dlc_sensors.py#L16-L44)) — control_board/env_sensors.py와 거의 동일. 양쪽 비교 후 더 견고한 쪽으로 통합 후 env_sensors.py 파일 자체는 폐기.

**중요 prerequisite — ADS1256 init graceful fallback 추가**:

현 [dlc_sensors.py:12-13](dlc_sensors.py#L12-L13)이 **module import 시점에 `ADC.ADS1256_init()`을 무조건 실행** → ADS1256 hw 미장착인 PCB 시스템에선 `import dlc_sensors` 자체가 exception. env 함수도 못 씀.

다른 hw들은 이미 graceful 처리됨 (HDC302x/DHT11/MPU6050 모두 try/except). ADS1256만 누락:

| 센서 | 미장착 시 동작 |
|---|---|
| **ADS1256** | ❌ **현재: import 시점에 fail** |
| HDC302x ([line 16-25](dlc_sensors.py#L16-L25)) | ✓ None 반환 |
| DHT11 ([line 28-36](dlc_sensors.py#L28-L36)) | ✓ None 반환 |
| MPU6050 ([line 49-55](dlc_sensors.py#L49-L55)) | ✓ None 반환 |

수정안:

```python
# dlc_sensors.py 상단 — ADS init도 graceful fallback
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

def _collect_adc_samples(n=30):
    if not _ADC_AVAILABLE:
        return None
    return [_ADC.ADS1256_GetAll() for _ in range(n)]

def get_coolant_temp(ad_index, adc_samples=None):
    if not _ADC_AVAILABLE:
        return None
    # ... 기존 로직

def poll_coolant(rd):
    if not _ADC_AVAILABLE:
        return    # PCB path에선 어차피 호출 안 됨
    # ... 기존 로직
```

env 함수들(get_air_temp/humit/chassis_stabil)은 이미 ADS와 무관 — 변경 불필요.

**효과**:
- PCB 시스템(ADS1256 없음): `import dlc_sensors` 성공 → `update_env(rd)` 정상 동작
- Legacy 시스템(ADS1256 있음): 변화 없음
- 개발 PC: 둘 다 없어도 import 가능 (테스트 용이성)

**Public API 추가/정리**:

```python
# dlc_sensors.py (기존 함수 유지 + 일괄 update 함수 추가)

# 기존 — 그대로 유지
def get_coolant_temp(ad_index, adc_samples=None): ...
def get_coolant_leak_detection(adc_samples=None): ...
def get_coolant_level_detection(adc_samples=None): ...
def get_air_temp(): ...           # ★ HDC302x 우선, DHT11 fallback (env_sensors 패턴 흡수)
def get_air_humit(): ...          # ★ HDC302x 우선, DHT11 fallback
def get_chassis_stabil(): ...

# 신규 — 통합 entrypoint
def update_env(rd):
    """RPi 직결 env 센서 일괄 read + Redis SET. PCB/ADS1256 driver 무관 호출."""
    t = get_air_temp()
    if t is not None: rd.set('air_temp', round(t, 1))
    h = get_air_humit()
    if h is not None: rd.set('air_humit', round(h, 1))
    s = get_chassis_stabil()
    if s is not None: rd.set('chassis_stabil', s)
```

**왜 driver와 분리?**:
- PCB는 Modbus로 NTC/leak/level read 가능하지만 **air_temp/humit/gyro에는 접근 경로가 없음** — RPi의 I2C/GPIO 핀에 직결돼야 함
- 따라서 driver 종류와 무관하게 RPi에서 별도 read → driver-orthogonal
- `dlc_sensors.update_env(rd)`는 PCBDriver와 ADS1256Driver 어느 path든 동일하게 호출
- 또한 `dlc_sensors.get_coolant_*` 함수들은 ADS1256Driver 내부에서 호출 (PCBDriver는 안 씀)

### `exporter/pcb_config.yaml` (control_board/config.yaml 이동 + 확장)

기존 PCB 운용 knob + 신규 cooling control 섹션 추가. `wiring.ntc`는 machine_config.py와 정보 중복이지만 **운용 시 참조 편의를 위해 그대로 유지** (단일 source는 machine_config.py).

```yaml
# 유지 (PCB backend 운용 파라미터)
modbus: {...}
loop:
  cycle_seconds: 1
pwm_freq: {...}

initial_pwm_duty:
  pump:
    ch1: 600          # ACTIVE 시 60% (기존 유지)
    ch2: 600
    ch3: 600
    ch4: 600
  fan:
    ch7: 80           # baseline 8% (영구 회전, 무음)
    ch8: 80
    ch9: 80
    ch10: 1000        # RPi cooling fan, always 100%

# 신규 — STANDBY 시 idle duty
standby_duty:
  pump: 100           # 10% (NTC 순환 유지)
  fan: 80             # 8% (영구 회전 baseline)

# 신규 — 부팅 시 fan cold start kick
fan_cold_start:
  initial_duty: 100   # 10% — 실측 검증된 cold start 최소
  initial_seconds: 3  # 회전 확실히 시작될 때까지
  # 이후 fan_curve.min_duty(=80, 8%)로 자연 ramp down

# 신규 — Cooling state 게이팅 임계
gating:
  active_entry:
    outlet_above_c: 30
    delta_t_above_c: 1.0
  standby_exit:
    outlet_below_c: 27            # 3°C hysteresis
    delta_t_below_c: 0.3          # noise floor × 6배
    require_stable_seconds: 1800  # 30분 연속 idle 유지
    minimum_active_seconds: 1800  # ACTIVE 진입 후 최소 30분 hold

# Fan curve — min_duty 변경 (5% → 8% baseline과 일치)
fan_curve:
  min_temp: 30        # ASHRAE W3 공급수 상한 근사
  max_temp: 60
  min_duty: 80        # 8% — STANDBY baseline과 연속 (smooth transition)
  max_duty: 1000

comm: {...}
pump:
  max_flow_lpm: 16
  flow_multiplier: 1.47

wiring:
  ntc:                            # machine_config.py와 정보 중복 — 참조 편의용 유지
    inlet1: 13                    # (코드에서는 machine_config.COOLANT_CHANNELS_PCB 사용)
    outlet1: 14
    outlet2: 15
    inlet2: 16
  din: {level_bit: 1}
  ain: {leak_ch: 8, leak_threshold_v: 2}
  pulse: {fan_tach_chs: [8, 9]}
  pwm: {pump_ch: [...], fan_ch: [7, 8, 9]}
```

**구분 기준**: "machine 모델이 바뀌면 같이 바뀌는가?" → Yes면 machine_config.py, No면 pcb_config.yaml.

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
SupplementaryGroups=dialout      # /dev/serial0, /dev/ttyUSB0 접근

[Install]
WantedBy=multi-user.target       # 부팅 시 자동 시작
```

`pcb_bootstrap.service` + `pcb_watcher.service` + `control_board.service` 폐기. 단일 service이므로 부팅 안무 단순화.

---

## 통합 전/후 비교

### 통합 전

```
src/
├── exporter/
│   ├── data_crawler.py          ← legacy backend main loop (단일 파일)
│   ├── dlc_sensors.py           ← ADS1256 + RPi I2C/GPIO 모두
│   ├── machine_config.py        ← legacy 채널 매핑만
│   └── sensor_exporter.py       ← Prometheus exposition
└── control_board/
    ├── main.py / main_loop.py / pcb_bootstrap.py / pcb_watcher.py
    ├── polling.py / controller.py
    ├── env_sensors.py           ← RPi I2C/GPIO (HDC302x 우선 — dlc_sensors와 중복)
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
│   ├── dlc_sensors.py           ← ★ RPi 직결 센서 (현재 그대로 + entry 함수 2개 추가)
│   │                              ADS1256 coolant + I2C/GPIO env (HDC302x/DHT11) + MPU6050
│   │                              poll_coolant(rd), update_env(rd) entry 신규
│   ├── pcb_driver.py            ← ★ 신규 — PCB hw I/O 단일 파일
│   │                              현 polling.py + modbus_client.py + registers.py + pcb_bootstrap.py 흡수
│   │                              class PCBDriver + def probe_pcb() 포함
│   ├── pcb_control.py           ← ★ 신규 — PCB cooling 정책 단일 파일
│   │                              FanCurveController + CoolingStateTracker
│   │                              현 controller.py 흡수 + state machine 신규 추가
│   ├── machine_config.py        ← ★ PCB / ADS1256 채널 매핑 두 dict
│   ├── pcb_config.yaml          ← (control_board/config.yaml 이동 + 신규 cooling control 섹션 추가)
│   ├── redis_keys.py            ← (control_board에서 이동, 통합)
│   └── sensor_exporter.py       ← (변경 없음)
└── control_board/               ← 폐기 (모든 코드 src/exporter/로 이동)

systemd:
└── data_crawler.service         ← ★ 단일 service (기존 명칭 유지)
                                    pcb_bootstrap + pcb_watcher + control_board service 폐기
```

| 변경 분량 | 전 | 후 |
|---|---|---|
| Service unit | 4개 (pcb_bootstrap + pcb_watcher + control_board + data_crawler) | 1개 (data_crawler, 명칭 유지) |
| Python 패키지 | 2개 (exporter + control_board) | 1개 (exporter, control_board 폐기) |
| Channel mapping 단일 source | 분산 + 명확하지 않음 | machine_config.py 단일 source. pcb_config.yaml의 wiring.ntc는 참조용 |
| 환경 센서 코드 | 2곳 중복 | 1곳 |
| 메인보드 의존성 | 메인보드 OFF → PCB OFF → 모니터링 끊김 | **자율 (PDB 12V + 냉각수 기반 제어)** |
| Sentinel 표현 | 두 backend 다름 (None vs -999) | 그대로 (각 backend 내부에서 sensor failure 시 DEL 처리) |

---

## 의사결정 포인트 요약

### 코드 구조

| 결정 | 선택 | 근거 |
|---|---|---|
| Wiring 위치 | machine_config.py (PCB 매핑 + Legacy 매핑) | machine 변천사를 한 곳에서 관리. config.ini는 user-facing minimal 유지 |
| 채널 매핑 자료구조 | 머신별 dict 두 개 (`COOLANT_CHANNELS`, `COOLANT_CHANNELS_PCB`) | PCB와 Legacy가 동일 패턴 (`{머신: {logical: 채널}}`)으로 평행 선언 |
| pcb_config.yaml 잔존 항목 | PCB 운용 knob (PWM duty, fan_curve, comm, modbus port, AIN/DIN/Pulse 매핑) + 신규 cooling control 섹션 | "PCB가 있는 경우에만 의미 있는 값" — backend-specific |
| Backend probe 시점 | 부팅 시 1회 (현 pcb_bootstrap 로직 흡수) | PCB는 일단 장착되면 영구 → runtime 재probe 불필요. pcb_watcher 폐기 |
| 환경 센서 코드 | **dlc_sensors.py 단일 source** (env_sensors.py 폐기) | RPi 직결 센서(ADS1256 + I2C/GPIO + MPU6050)를 한 파일에 통합. env_sensors의 HDC302x I2C 우선 로직만 흡수 |
| Service 명 | `data_crawler.service` 그대로 유지 | 기존 unit 명 유지로 systemd 호환성 보장. 역할만 확장 |
| Entry point | `exporter/data_crawler.py` 그대로 유지 | 사용자/스크립트에서 참조하는 path 변경 없음 |
| Package home | `src/exporter/` | 기존 패키지 그대로. control_board/ 폐기하고 exporter/로 흡수 |
| Sentinel 표현 | 기존 그대로 (`None` legacy, `-999` PCB) — 필요 시 backend 내부에서 처리 | 핵심 진실은 dict 선언. Sentinel은 단순 sensor failure handling만 담당 |

### Cooling 제어 전략

| 결정 | 선택 | 근거 |
|---|---|---|
| Cooling 활성화 신호 | **냉각수 온도 기반 (메인보드 신호 무관)** | USB gadget 19pin 호환성 issue 회피, PDB 12V 독립 전원 시나리오 대응 |
| 활성화 임계 | outlet > 30°C **OR** ΔT_corrected > 1°C | 30°C: ASHRAE W3 공급수 상한 근사 (STANDBY outlet≈inlet). ΔT 1°C: 200W 이상 모든 부하 catch (저-duty 펌프 효과) |
| 상태 머신 | **STANDBY / ACTIVE 2상태 + asymmetric hysteresis** | 산업 표준 (태양열 DTC, CDU). 진동 방지 |
| STANDBY 복귀 조건 | outlet < 27°C AND ΔT < 0.3°C 가 30분 연속 유지 + ACTIVE 후 최소 30분 hold | 하루 0~2회 전환만 발생, chattering 0 |
| **STANDBY pump duty** | **10%** (NTC 순환 유지) | ~5W 미미. NTC 신호 살림. PMP-500 정격의 충분한 idle |
| **STANDBY fan duty** | **8% (영구 회전, 절대 정지 X)** | Cold start stall 노이즈 원천 차단. 1500 RPM ≈ 25 dBA 무음 수준 |
| ACTIVE pump duty | 60% (config 기본 — 변경 없음) | Fixed-duty 운용 정책 유지 (유량 센서 없음) |
| ACTIVE fan duty | fan_curve (8~100%, outlet 30~60°C 선형) | DC 표준 활성화 점 30°C, baseline과 연속 |
| Fan cold start kick | **부팅 시 10% × 3초 → 8% 정착** | 실측 검증 (10%로 cold start 가능). stop→start stall 회피 |

---

## Critical files

수정 (통합 시):
- [machine_config.py](machine_config.py) — `COOLANT_CHANNELS_PCB` 신규 추가, 기존 `COOLANT_CHANNELS`는 유지
- [data_crawler.py](data_crawler.py) — entrypoint 확장 (driver probe + 단일 main loop + CoolingStateTracker)
- [dlc_sensors.py](dlc_sensors.py) — **유지 및 확장**. control_board/env_sensors.py의 HDC302x I2C 지원 흡수. `update_env(rd)` 통합 entrypoint 추가
- `../configure/daemons/gadgetini/data_crawler.service` — `[Install] WantedBy=multi-user.target` 명시 (확인 필요)

이동 (control_board → exporter):
- `../control_board/redis_keys.py` → `redis_keys.py` (기존 키와 통합)
- `../control_board/config.yaml` → `pcb_config.yaml` (신규 cooling control 섹션 추가. wiring.ntc는 참조용 유지)
- `../control_board/modbus_client.py` + `registers.py` + `polling.py` + `pcb_bootstrap.py` → **`pcb_driver.py` 단일 파일로 통합**
- `../control_board/controller.py` → **`pcb_control.py`** 의 FanCurveController로 흡수
- `../control_board/env_sensors.py` → **dlc_sensors.py에 HDC302x 로직만 흡수** (별도 파일 안 만듦)

ADS1256 coolant 함수는 `dlc_sensors.py`에 그대로 유지 — 별도 wrapper 폴더 불필요.

폐기:
- `../control_board/main.py` (entrypoint를 data_crawler.py로 이전)
- `../control_board/main_loop.py` (data_crawler.py로 흡수)
- `../control_board/pcb_bootstrap.py` (probe 로직을 data_crawler.py에 흡수)
- `../control_board/pcb_watcher.py` (PCB는 영구 장착 가정 → runtime 재probe 불필요)
- `../control_board/` 패키지 자체 (모든 파일 이동/흡수 후)
- `../configure/daemons/gadgetini/pcb_bootstrap.service`
- `../configure/daemons/gadgetini/pcb_watcher.service`
- `../configure/daemons/gadgetini/control_board.service`

신규:
- `pcb_driver.py` (class PCBDriver + def probe_pcb() — Modbus + register 맵 + read/write 통합)
- `pcb_control.py` (FanCurveController + CoolingStateTracker — PCB cooling 정책 단일 파일)

폐기 (control_board에서):
- `../control_board/env_sensors.py` (HDC302x 로직만 dlc_sensors.py에 흡수 후 파일 자체 삭제)

변경 없음:
- `../display/config.ini` — user-facing minimal 그대로
- [sensor_exporter.py](sensor_exporter.py) — Redis 키 unchanged (단 `cooling_state` 키 신규 추가는 노출 검토)

---

## Verification (실제 구현 단계에서)

이 문서 범위는 설계. 구현 시점의 검증 항목 미리 정리:

### 센서 경로 분기 / 채널 매핑

1. **Legacy path (dg5w gen1, gen2)**: ADS1256 장착된 구 hw에서 `data_crawler.service` 단일 실행 → coolant_temp_inlet1/outlet1 값이 통합 전과 동일
2. **Legacy path (dg5r gen2)**: 4채널 모두 SET 확인
3. **PCB path (dg5w/dg5r gen3)**: PCB 장착된 hw에서 동일 `data_crawler.service`가 PCB 경로로 자동 분기, coolant_temp_* + comm_status + fan duty 정상
4. **PCB 시스템에서 ADS1256 미장착 케이스**:
   - `import dlc_sensors` 성공 확인 (graceful fallback 검증)
   - `dlc_sensors.update_env(rd)` 정상 동작 → air_temp/humit Redis SET
   - `dlc_sensors._ADC_AVAILABLE == False` 확인
   - `poll_coolant(rd)` no-op (예외 안 남)
5. **Probe fallback**: PCB 케이블 분리 → service 재시작 → Legacy 경로로 분기
6. **machine_config 검증**:
   - PCB path: `COOLANT_CHANNELS_PCB['dg5w']` → inlet1/outlet1만 SET 확인
   - PCB path: `COOLANT_CHANNELS_PCB['dg5r']` → 4개 다 SET 확인
   - Legacy path: `COOLANT_CHANNELS[MACHINE]`로 머신별 ADS 채널 매핑 정상 동작
7. **Sensor exporter 무영향**: Prometheus :9003 endpoint의 metric 셋이 통합 전후 동일

### Cooling state machine (PCB driver path만 적용. Legacy hw는 해당 없음)

7. **부팅 시 fan cold start**:
   - 부팅 직후 3초간 fan duty = 100 (10%) → 이후 fan duty = 80 (8%) 정착
   - Tach RPM이 0 이상 (회전 시작 확인)
8. **STANDBY 운용 (서버 OFF 상태)**:
   - 펌프 duty readback = 100 (10%)
   - 팬 duty readback = 80 (8%)
   - 팬 RPM > 0 (영구 회전 확인)
   - 모든 coolant_temp_*, leak, level 키 정상 SET
9. **ACTIVE 진입 (outlet > 30°C 또는 ΔT > 1°C)**:
   - 펌프 duty → 600 (60%)
   - 팬 duty → fan_curve 값 (outlet 30°C이면 80, 60°C이면 1000)
   - `cooling_state` Redis 키 = `'active'`
10. **STANDBY 복귀 (outlet < 27°C AND ΔT < 0.3°C 가 30분 유지)**:
    - 30분 grace 동안 ACTIVE 유지
    - 30분 + minimum hold 만족 시 STANDBY 전이 (펌프 10%, 팬 8%)
    - 부분 만족 (예: 25분만 stable) 시 STANDBY 진입 안 함
11. **Chattering 방지**:
    - 서버 부하 변동으로 outlet이 28~32°C 흔들려도 ACTIVE 유지 (STANDBY 복귀 outlet 27°C 임계 미달성)

### NTC noise

12. **노이즈 baseline**: 단일 NTC stdev < 0.05°C, ΔT stdev < 0.1°C 유지 (재실측)
13. **운용 중 false-positive 모니터링**: STANDBY 상태에서 ΔT가 1°C에 가깝게 떠 있다면 NTC 개체차 systematic offset 의심 → 보정 로직 재도입 검토

---

## 후속 작업 (이번 설계 외)

- 점진적 마이그레이션 단계별 PR plan
- (선택) Cooling state의 하드웨어 보강 — `host_ttl` 같은 software 신호도 보조로 활용 (USB gadget 작동하는 머신만)
- dlc_sensors의 dummy 모드 옵션 (현재 aiexpo 브랜치의 env_sensors.py에만 존재) → 통합 시 env-flag 토글로 dlc_sensors에 일반화 검토

---

## 개선 필요 항목 (TODO — 후속 검토)

이 설계는 첫 draft이며 다음 항목들은 추가 검토·결정 필요:

- [ ] backend probe 실패 시 fail-safe 동작 (예: PCB 응답 없음 + ADS1256도 미장착 → 어떻게 처리?)
- [ ] `pcb_config.yaml` 내 wiring.din/ain/pulse/pwm 섹션도 dg5w/dg5r마다 다를 수 있는지 확인 → 다르다면 machine_config.py로 추가 이동 검토
- [ ] `redis_keys.py` 통합 시 양 패키지 키 상수 충돌·누락 확인 (e.g., COMM_STATUS, PWM_DUTY_* 키들의 owner 명확화)
- [ ] Cooling state 임계값 (5°C/30분 hysteresis) 운용 검증 후 완화 검토 (3°C/15분 등)
- [ ] NTC 개체차 systematic offset 운용 검증 — 실측 0.87°C는 측정 오류일 수 있음. STANDBY에서 ΔT가 일관되게 큰 값으로 떠있으면 재측정 후 보정 로직 재도입 검토
- [ ] Fan cold start kick 자동 재시도 로직 — 부팅 외에도 fan_rpm이 0으로 떨어지면 (먼지/일시 dip) cold start 재실행 검토
- [ ] 마이그레이션 단계별 PR plan 작성 (회귀 위험 분산)
- [ ] 통합 전 in-flight production 영향도 평가 (특히 dg5r gen3 운용 중인 머신)
- [ ] 통합 후 control_board/ 패키지 폐기 시점 — git history 보존 차원에서 archive 디렉토리로 이동할지, 완전 삭제할지
- [ ] `cooling_state` Redis 키를 sensor_exporter.py에서 Prometheus metric으로 노출할지 결정 (Grafana 대시보드 표시 위해)
