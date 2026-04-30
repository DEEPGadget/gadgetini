# control_board

Gadgetini의 PCB 제어보드 통합 모듈. 모니터링 값에 따라 액추에이터를 자동 제어한다.

> dg5R 와이어링 확정 (§ 통신 구조 — dg5R 와이어링). 결선 완료 후 통합 테스트 단계로 이행 예정 (§ 검증).

## Context

기존 gadgetini는 Raspberry Pi가 ADS1256 SPI ADC + I2C/GPIO로 센서를 직접 읽기만 하는 read-only 시스템이었다. 자체 개발 PCB 제어보드(절연 RS485 Modbus RTU)가 도입되면서:

1. **센서 경로 이전** — NTC 쿨란트 온도, 누수/레벨 입력이 ADS1256 → PCB로 이동.
2. **자동 폐루프 제어** — 팬·펌프 PWM/Tach/Fault를 센서값 기반 알고리즘으로 자동 제어.
3. **알람 감지** — threshold 기반 이상 감지 (제어 명령은 생성하지 않음, UI 표시·이력 전용).

구버전 서버는 PCB 미장착이므로 **동일 image가 신/구 hw 모두에서 동작**해야 한다.

## Architecture

### 부팅 시 분기

```
                      systemd boot
                           │
                  ┌────────▼────────┐
                  │ pcb_bootstrap   │  oneshot, RemainAfterExit
                  │  .service       │  Modbus probe:
                  │                 │   port × baud =
                  │                 │   {/dev/serial0, /dev/ttyUSB0}
                  │                 │   × {115200, 9600}
                  └────┬───────┬────┘
                       │       │
              probe ok │       │ all probes fail
                       ▼       ▼
       ┌───────────────────┐   ┌──────────────────┐
       │ control_board     │   │ data_crawler     │  (기존, 무수정)
       │  .service (NEW)   │   │  .service        │
       └─────────┬─────────┘   └────────┬─────────┘
                 │                      │
                 └──────► Redis ◄───────┘
```

`data_crawler.service`(구hw)와 `control_board.service`(신hw)는 **mutually exclusive**. `pcb_bootstrap.service`가 부팅 시 한 번만 결정하고 그 후 변경하지 않는다.

> Probe 순서는 `port` 우선 (`/dev/serial0` → `/dev/ttyUSB0`), 각 port에서 baud는 `[115200, 9600]` 순. RS485 (UART3) 직결을 1차로, USB-RS485 어댑터를 fallback으로 둔다. baud는 보드 DIP6 설정(ON=115200 / OFF=9600) 어느 쪽이든 자동 인식. `control_board.main` 내부에서도 동일한 fallback 순회를 거쳐, bootstrap 통과 후 메인 루프 진입 시점에 보드 baud가 바뀌어도 재연결한다 ([pcb_bootstrap.py:15-16](pcb_bootstrap.py#L15-L16), [main.py:69-79](main.py#L69-L79), [config.yaml](config.yaml)).

### 메인 루프

단일 쓰레드. Modbus는 단일 시리얼 버스 — Read/Write 동시 불가. 모든 PCB 통신은 메인 루프 안에서 순차 실행.

cycle 당:

```
1. Polling
     → Modbus Read (센서 + 현재 PWM duty)
     → 디코딩 → Redis SET + Pub/Sub publish

2. RPi 직접 수집 센서 (HDC302x/DHT11 등)
     → air_temp / air_humit (dg5w 한정 chassis_stabil 추가)

3. 제어 알고리즘
     → 센서값 → PWM duty 결정
     → Modbus Write
```

> S-Curve 1초 ramping은 PCB 펌웨어가 자체 적용. 호스트는 raw target만 보내면 됨.
> Emergency 모드는 TODO. 도입 시 step 0으로 "전체 PWM=0, DOUT=0 후 skip" 추가.

### Redis Key

기존 [sensor_exporter.py](../exporter/sensor_exporter.py)와의 호환을 위해 **현행 flat key 명명 규칙 그대로 이어서 사용**한다. 새로 추가되는 키도 동일한 flat naming을 따른다 (prefix `:` 사용 안 함).

**기존 키 (control_board가 쓰는 측이 됨, 이름 변경 없음):**

| Key | 단위 | 설명 |
|---|---|---|
| `coolant_temp_inlet1` / `inlet2` | °C | 입수 온도 |
| `coolant_temp_outlet1` / `outlet2` | °C | 출수 온도 |
| `coolant_delta_t1` / `delta_t2` | °C | ΔT (inlet/outlet 페어 둘 다 valid 시에만 SET) |
| `coolant_leak` | 0/1 | 누수 (1=Leak) |
| `coolant_level` | 0/1 | 수위 (1=OK) |
| `air_temp` | °C | 장치 내부 온도 (DHT11/HDC302x — RPi I2C 직접) |
| `air_humit` | %RH | 장치 내부 습도 (RPi I2C 직접) |
| `chassis_stabil` | 0/1 | 섀시 안정 (MPU6050, dg5w 한정) |
| `host_stat` | 0/1 | host TTL 기반 online 여부 |

> NTC 미연결 채널은 키 자체를 SET하지 않음 (또는 DEL) → exporter 측이 `client.exists()` 게이트로 자연스럽게 제외 ([sensor_exporter.py:115-124](../exporter/sensor_exporter.py#L115-L124) 패턴 그대로).

**신규 키 (control_board가 추가):**

| 그룹 | 패턴 | 예시 |
|---|---|---|
| 통신 상태 | `comm_*` | `comm_status` (ok/timeout/disconnected), `comm_consecutive_failures`, `comm_last_error` |

> 임계 알람(쿨란트 온도, 누수, 수위, ΔT 등)은 control_board가 별도 키로 SET하지 않는다.
> Raw metric을 sensor_exporter가 이미 Prometheus로 노출하므로 Grafana alert rule에서 직접 평가 — 단일 source of truth.

### Prometheus 통합

기존 `sensor_exporter.service`가 Redis를 Pull로 수집해 시계열 적재. 기존 센서 키 + 신규 알람 키 노출 (sensor_exporter.py에 작은 패치 필요).

### 서비스 초기화

PCB Flash 저장 항목과 미저장 항목을 분리해서 다룬다 (보드 매뉴얼 §6).

**Flash 영구 저장 (보드에 이미 적용·고정됨, control_board 관여 없음):**
- PWM 주파수 (HR 12/13/14) — TIM1=1 kHz / TIM2=25 kHz / TIM8=25 kHz
- PWM 극성 (HR 16) — Active High 디폴트
- ADC 게인 (HR 19~26)

> Factory Reset(BT2 3초) 또는 보드 교체 시에만 재설정 필요.

**매 부팅 시 control_board가 적용 (Flash 미저장 항목):**
- 팬·펌프 PWM 초기 duty (HR 0~11)
- DOUT 초기 상태 (HR 15 또는 Coil 0~5)

→ `config.yaml`이 source of truth. systemd `Restart=always`로 전원 재인가 시 자동 재적용.

**PCB 전원 재인가 시에도 자동 재적용**: 호스트 메인보드에서 PCB만 단독으로 전원이 끊겼다 들어오는 경우(라즈베리파이는 살아있는 상태) PCB의 Flash 미저장 항목이 펌웨어 기본값으로 리셋된다. main loop가 polling 실패 → 복구 전이를 감지하면 `apply_initial_state`를 재호출 ([main_loop.py:48-60](main_loop.py#L48-L60)) — service 재시작 없이 펌프 duty / DOUT을 config 기준으로 복원.

### 알람

control_board는 **별도 알람 키를 생성하지 않는다**. raw 센서값(coolant_temp_*, coolant_leak, coolant_level, coolant_delta_t 등)은 sensor_exporter가 이미 Prometheus로 노출하므로 임계 평가는 **Grafana alert rule(또는 Prometheus alerting rule) 측에서 단일 처리**. 두 군데서 같은 임계를 관리하면 drift 위험만 커진다.

예외: `comm_status` (ok/timeout/disconnected) 는 control_board 내부 통신 카운터에서 파생되는 상태라 raw metric만으로 재구성할 수 없음 — 그래서 이 키만 자체 SET. Grafana 측에서 `comm_status != "ok"` 로 알람 가능.

비상정지 연동은 TODO.

### 환경 센서

PCB를 거치지 않고 RPi에 직접 연결된 센서들. control_board가 자체 처리해 Redis에 SET.

- **온습도** — DHT11 또는 HDC302x 중 부팅 시 감지된 한쪽 사용 ([dlc_sensors.py:44-49](../exporter/dlc_sensors.py#L44-L49) 패턴) → `air_temp`, `air_humit`.
- **자이로** — MPU6050, dg5w 한정. 거의 필요없는 데이터지만 기존 sensor_exporter 호환을 위해 키 유지 → `chassis_stabil`. init/read graceful fallback ([dlc_sensors.py:52-59](../exporter/dlc_sensors.py#L52-L59), [:150-169](../exporter/dlc_sensors.py#L150-L169) 패턴) — 미장착·라이브러리 미설치·통신 실패 어떤 경우든 죽지 않고 stable=1로 fail-safe. dg5r은 키 자체 SET 안 함.

### 펌프 유량 추정

유량 센서 미장착 → PWM duty + 펌프 토폴로지 multiplier로 1차 근사. 결과는 `coolant_flow_lpm` (L/min) Redis 키로 SET.

```
flow_lpm = max_flow_lpm × (avg_pump_duty / 1000) × flow_multiplier
```

현재 구성:
- **단일 펌프**: Koolance PMP-500 — `max_flow_lpm = 16` (12V @ H=0)
- **토폴로지**: 4 pumps = 2 series × 2 parallel loops
- **`flow_multiplier = 1.47`** — 직렬 2 펌프 효과 추정. 근거: D5 측정 사례 1.09 → 1.6 GPM ≈ 1.47× ([Martin's Liquid Lab dual-D5 series 분석](https://martinsliquidlab.wordpress.com/2011/04/26/pump-setup-series-vs-parallel/), [HardForum doubling D5](https://hardforum.com/threads/doubling-d5-for-flow.1992647/)). 병렬 루프 곱셈은 cold-plate 매니폴드 의존이라 보수적으로 생략 — 표시값은 per-loop 추정.

> **추정값**이라 ±20~50% 오차 가능. 향후 유량계 도입 시 실측 비교로 multiplier를 보정해야 한다 — 예: ΔT × Q × Cp 열량과 호스트 측 power consumption 매칭으로 derate 검증.

### 자동 제어 알고리즘

**펌프는 고정 duty 운용**. 부팅 시 `config.yaml`로 한 번 Write 후 변경하지 않는다. controller.py는 팬 duty만 outlet 온도 lookup으로 갱신.

가변 펌프 제어를 적용하지 않는 이유:

- **유량 센서 미장착** — duty를 낮췄을 때 실제 유량이 cold plate 임계 위를 유지하는지 검증할 수 없음. 측정 없는 가변 제어는 starvation → 핫스팟 → 쓰로틀링 리스크.
- **에너지 절감 효과 미미** — PMP-500 정격 32 W, 60% 운용 ≈ 12 W. 가변으로 절약되는 펌프 전력은 서버 부하(5~10 kW/node) 대비 무의미한 수준.
- **가변 제어의 목적은 ΔT 10~14 °C 윈도우 유지(ASHRAE TC 9.9 권장)인데, 유량 피드백 없이 폐루프 신뢰성 확보 불가** — 산업 연구에서도 유량 측정·VSP 기반 ΔT 추종이 표준 ([ScienceDirect 분석](https://www.sciencedirect.com/science/article/pii/S030626192501791X), [NVIDIA DGX SuperPOD 가이드](https://docs.nvidia.com/dgx-superpod/design-guides/dgx-superpod-data-center-design-h100/latest/cooling.html), [ASHRAE TC 9.9 Water-Cooled Servers white paper](https://www.ashrae.org/file%20library/technical%20resources/bookstore/whitepaper_tc099-watercooledservers.pdf)).

향후 유량 센서 도입 시 ΔT-cascade로 확장 가능. 도입 전 단계 옵션으로는 baseline 위로만 올리는 **boost-only** 패턴(예: ΔT > 15 °C 시 일시 +20%)이 starvation 리스크 없이 마진을 확보하는 안전한 방법.

**Fan curve (lookup table)**

| outlet | fan duty |
|---|---|
| < 30 °C | 20% |
| 30~40 °C | 40% |
| 40~50 °C | 65% |
| 50~60 °C | 85% |
| ≥ 60 °C | 100% |

단계 경계에서 ±1 °C hysteresis로 chattering 방지. PWM 변경 시 PCB가 자체 S-Curve 1초 보간하므로 호스트 측 추가 rate limit 불필요.

**Loop instance**

- dg5w: inlet1+outlet1 1조 → instance 1개
- dg5r: 2조 → instance 2개 독립 운용 (동일 파라미터 출발, 시스템 검증 후 비대칭 튜닝 가능)

> Stage 2 (outlet PI), Stage 3 (cascade), anti-windup/rate-limit 가드레일은 후속 단계 — 시스템 검증 후 재검토.

## 통신 구조 — dg5R 와이어링

| 신호 | PCB 입출력 | Modbus 주소 | Redis 키 |
|---|---|---|---|
| 누수 (D11→AIN8) | AIN CH8 | IR 39 (0.01V, threshold 5V) | `coolant_leak` |
| 수위 (D12) | DIN2 (bit 1) | IR 25 | `coolant_level` |
| Inlet1 (NTC1) | CH13 | IR 28 | `coolant_temp_inlet1` |
| Outlet1 (NTC2) | CH14 | IR 29 | `coolant_temp_outlet1` |
| Outlet2 (NTC3) | CH15 | IR 30 | `coolant_temp_outlet2` |
| Inlet2 (NTC4) | CH16 | IR 31 | `coolant_temp_inlet2` |
| 펌프 4대 PWM 출력 | CH1~4 (TIM1) | HR 0~3 | (입력만 — 동일 duty 적용) |
| 펌프 유량 (추정) | — (duty 기반) | — | `coolant_flow_lpm` (L/min) |
| 팬 2채널 PWM 출력 | CH9~10 (TIM8) | HR 8~9 | (입력만) |
| 팬 2채널 Tach 입력 | Pulse CH9~10 | IR 21~22 | `fan_rpm_1`, `fan_rpm_2` |
| 온/습도 | (PCB 미경유) RPi I2C | — | `air_temp`, `air_humit` |
| 자이로 (사용 안 함) | — | — | `chassis_stabil` (dg5R는 SET 안 함) |

ΔT 자동 계산: inlet/outlet 페어가 둘 다 valid한 cycle에만 SET → `coolant_delta_t1`, `coolant_delta_t2`. 한 쪽이라도 -999/미연결이면 키 자체 DEL.

## Folder Layout

```
src/control_board/
├── README.md             ← 본 문서
├── config.yaml           # 초기 PWM duty, fan_curve, threshold, slave_id, baud, serial port, wiring
├── install.sh            # 패키지 설치 + systemd unit 등록 + bootstrap enable
│
├── __init__.py           # 패키지 마커
├── main.py               # 엔트리포인트 (python3 -m control_board.main)
├── main_loop.py          # 메인 루프 (Polling → 환경 센서 → Controller)
│
├── modbus_client.py      # 단일 시리얼 버스 wrapper, signed int16 헬퍼
├── registers.py          # PCB Modbus 레지스터 맵 상수
├── redis_keys.py         # Redis 키 상수 모음
│
├── polling.py            # Modbus Read (NTC/DIN/Pulse) → Redis SET + ΔT 계산
├── controller.py         # outlet 온도 → 팬 duty lookup, ±1°C hysteresis, 펌프 고정
├── env_sensors.py        # HDC302x/DHT11 자동 감지 + MPU6050 stub (graceful fallback)
│
├── pcb_bootstrap.py      # 부팅 시 PCB probe → control_board.service 시작
└── test_fan_curve.py     # 페이크 데이터 시나리오 검증 (controller 로직 검증용, § 검증 참고)
```

systemd unit 파일 (위치는 기존 컨벤션 따름):

```
src/configure/daemons/gadgetini/
├── pcb_bootstrap.service    # oneshot, multi-user.target에 wired
└── control_board.service    # WantedBy 없음 (bootstrap이 직접 start). Type=simple, Restart=always.
                             # Conflicts=data_crawler.service → 자동 mutual exclusion.
```

기존 `data_crawler.service`는 **무수정 유지** (Phase 1 additive). `[Install] WantedBy=multi-user.target` 그대로 두되, `control_board.service`의 `Conflicts=`로 mutual exclusion이 작동 — 신hw 부팅 시 bootstrap이 control_board를 start하는 즉시 systemd가 data_crawler를 자동 stop. 구hw에선 PCB 미감지 → control_board 미시작 → data_crawler 그대로 운용.

## PCB 통신 사양 요약

상세는 보드 매뉴얼 참조. 게이트웨이 코드 작성에 직접 영향 있는 항목만 발췌.

| 항목 | 값 |
|---|---|
| 포트 | RS485 (UART3, 절연) — Pi에서는 `/dev/serial0` |
| 보조 포트 | USB CDC — CRC-16으로 Modbus/CLI 자동 판별 (개발/디버그용) |
| 프로토콜 | Modbus RTU |
| Baud | DIP6 OFF=9600, ON=115200 (출하 시 ON 권장) |
| Slave ID | DIP1~5 (1~31, 0이면 자동 1) |
| Frame | 8N1 |
| Duty 포맷 | 0~1000 (0.1% 단위, Active Low) |
| Freq 포맷 | kHz 정수 |
| 동작 특성 | PWM 변경 시 PCB가 자체 S-Curve 1초 보간 |

PCB 자체 보호 (펌웨어): OCP / SCP / OTP — 채널별 자동 차단. 자동 재시도 정책은 펌웨어 사양 TBD.

## 액추에이터 사양

게이트웨이 코드 작성·전력 예산·RPM 환산에 영향 있는 항목만 발췌.

### PCB 출력 채널 매핑 (실보드 기준)

| 타이머 | HR duty | HR freq | 채널 | 커넥터 | 출력 형태 | 운용 주파수 | 용도 |
|---|---|---|---|---|---|---|---|
| TIM1 | HR 0~3 | HR 12 | CH1~4 | 3핀 (T/G/V) | 가변 전압 출력 (5~100% duty → 6~12 V DC) | **1 kHz** (PCB 매뉴얼 §10.1 권장 — 내부 벅 컨버터 필터 기준) | **펌프** |
| TIM2 | HR 4~7 | HR 13 | CH5~8 | 4핀 (G/V12/T/PWM) | Intel 4-wire PWM 직결 | **25 kHz** (가청 영역 회피) | **팬** |
| TIM8 | HR 8~11 | HR 14 | CH9~12 | 4핀 (G/V12/T/PWM) | Intel 4-wire PWM 직결 | **25 kHz** | **팬** |

위 운용 주파수는 PCB Flash에 영구 저장되어 매 부팅 자동 복원된다. control_board는 freq를 set할 필요 없고 duty(HR 0~11)만 다룬다. T 핀은 입력 — Tach 신호를 PCB Pulse Freq 입력 채널(IR 13~24)로 받음.

### Pump — Koolance PMP-500

| 항목 | 값 |
|---|---|
| 종류 | Brushless DC, magnetic centrifugal |
| 정격 전압 | 12 VDC (운용 6~12 VDC) |
| 최대 소비전력 | 32 W |
| 최대 유량 | 16 L/min (4.2 GPM) |
| 최대 양정 | 7.5 m H₂O (24.6 ft) |
| 최대 동작 온도 | 75 °C |
| 전기 커넥터 | 4-pin Molex (전원) + 3-pin (Tach, Yellow lead) |
| 속도 제어 | PCB **TIM1 (CH1~4, HR 0~3)** 가변 전압 출력에 직결. duty → 전압 매핑은 PCB 매뉴얼 §10.1. 외부 회로 불필요. |
| Tach | 1-lead pulse output (펄스/회전 미명시 → 실측 환산) |
| 수명 | 30,000 hrs MTBF |

### Fan — Cooltron FD8038B12W7-63-4J

| 항목 | 값 |
|---|---|
| 사이즈 | 80 × 80 × 38 mm, dual ball bearing |
| 정격 전압 | 12 VDC (운용 6~13.8 V, 기동 6 V @ 25 °C) |
| 정격 전류 | 1.86 A (max), actual 1.55 A |
| 정격 소비전력 | 18.6 W (max 22.32 W) |
| 정격 RPM | 7500 ±10% |
| 최대 풍량 | 105.3 CFM |
| 최대 정압 | 34.8 mm-H₂O |
| 소음 | 62 dB(A) |
| 와이어 | Red(+), Black(−), Yellow(FG=Tach), Blue(PWM) — 4-wire |
| **PWM 입력** | PCB **TIM2 (CH5~8, HR 4~7) + TIM8 (CH9~12, HR 8~11)**, 1~25 kHz 가변, **운용 25 kHz** (High 5.0 V / Low 0.4 V), duty 0~100% |
| **Tach (FG)** | **2 pulses/rotation** → RPM = Hz × 30 |
| 동작 온도 | −10 ~ +70 °C |
| 보호 | Locked rotor (1초 후 자동 차단 + 자동 재시도), polarity protection |
| 수명 | 70,000 hrs @ 40 °C |

> 팬(TIM2/TIM8)만 25 kHz로 변경 후 Save (HR 13/14 = 25000, HR 17 = 0x01). 펌프(TIM1)는 보드 매뉴얼 권장값 1 kHz 디폴트 유지.
> Tach는 모두 PCB Pulse Freq 입력 채널로 받음. 팬 RPM = Hz × 30 (2 p/r). 펌프는 펄스/회전 미명시 → 실측 환산.

## 검증

단계적 테스트로 시스템 동작을 검증한다. 액추에이터 결선 진척에 맞춰 후속 테스트를 추가.

### Phase 1 — 결선 전 로직 검증 (현재 단계)

액추에이터 미결선 상태에서 controller / lookup / hysteresis / Modbus write 경로가 의도대로 동작하는지 검증.

- **`test_fan_curve.py`** — Redis `coolant_temp_outlet1`에 페이크 outlet 온도를 주입하고 `FanCurveController.update()`를 호출, PCB HR 8/9에 쓰인 fan duty를 readback해서 시나리오별로 일치하는지 확인. 상승·하강·boundary hysteresis (50→49 °C 유지, 48.9 °C 강하) 11개 시나리오 PASS 검증 완료.
- 단발 read 검증 (NTC 1번 수온 26 °C 측정, IR 32~39 voltage 매핑, DIN bit 토글 등) — 임시 스크립트로 확인.

### Phase 2 — 결선 후 통합 검증 (예정)

펌프·팬·누수·수위 센서 결선 완료 시점에 진행:

1. **펌프 유량 multiplier 보정** — TIM1 duty 0~100% 스윕하면서 외부 유량계로 실제 L/min 측정 → 현 추정식 (`max_flow × duty/1000 × 1.47`) 대비 오차 확인 → `pump.flow_multiplier` 또는 `max_flow_lpm` 보정. 정밀 검증은 ΔT × Q × Cp 열량과 호스트 측 power consumption 매칭으로 cross-check.
2. **팬 RPM 검증** — TIM8 duty 0~100% 스윕, Pulse CH9/10 Hz × 30 = RPM이 데이터시트(7500 RPM ±10%)와 일치하는지.
3. **fan curve 폐루프** — Inlet1/Outlet1에 외부 열 부하 인가하면서 outlet 온도 상승 → controller가 자동으로 fan duty 단계 상승 → 실제 RPM 변화까지 end-to-end 확인.
4. **임계 알람** — Grafana alert rule 측에서 raw metric (coolant_temp_outlet, coolant_leak, coolant_level, coolant_delta_t, air_temp 등) 임계 평가가 의도대로 동작하는지 확인. control_board는 별도 알람 키를 만들지 않음.
5. **통신 fallback** — RS485 케이블 분리 → `comm_consecutive_failures` 카운트 → `comm_status` 가 'timeout' → 'disconnected' 로 단계적 전이 → 재연결 시 'ok' 자동 복구.
6. **bootstrap 부팅 흐름** — 재부팅 후 pcb_bootstrap → control_board → data_crawler 자동 stop → 메인 루프 진입까지 자동 검증.

각 항목은 `test_*.py` 형태 스크립트로 확장 — 결선 진척에 따라 점진적으로 추가.
