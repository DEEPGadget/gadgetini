# control_board

Gadgetini의 PCB 제어보드 통합 모듈. 모니터링 값에 따라 액추에이터를 자동 제어한다.

> 센서/모델 수량/채널 매핑은 미확정 — 와이어링 도면 확정 후 본 문서에 통신 구조 섹션 추가.

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
                  │  .service       │  Modbus probe on /dev/serial0
                  └────┬───────┬────┘
                       │       │
              probe ok │       │ probe fail
                       ▼       ▼
       ┌───────────────────┐   ┌──────────────────┐
       │ control_board     │   │ data_crawler     │  (기존, 무수정)
       │  .service (NEW)   │   │  .service        │
       └─────────┬─────────┘   └────────┬─────────┘
                 │                      │
                 └──────► Redis ◄───────┘
```

`data_crawler.service`(구hw)와 `control_board.service`(신hw)는 **mutually exclusive**. `pcb_bootstrap.service`가 부팅 시 한 번만 결정하고 그 후 변경하지 않는다.

### 메인 루프

단일 쓰레드. Modbus는 단일 시리얼 버스 — Read/Write 동시 불가. 모든 PCB 통신은 메인 루프 안에서 순차 실행.

cycle 당:

```
1. Polling
     → Modbus Read (센서 + 현재 PWM duty)
     → 디코딩 → Redis SET + Pub/Sub publish
     → 알람 threshold 검사 → SET/DEL 알람 키

2. RPi 직접 수집 센서 (DHT11/HDC302x 등)
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
| 알람 | `alarm_<항목>` | `alarm_coolant_temp_warning`, `alarm_leak_detected`, `alarm_water_level_critical`, `alarm_comm_disconnected` 등 |
| 통신 상태 | `comm_*` | `comm_status` (ok/timeout/disconnected), `comm_consecutive_failures`, `comm_last_error` |

> 정확한 알람 키 목록은 와이어링 + threshold 확정 시 결정. sensor_exporter는 신규 알람 키 노출용 작은 패치 필요.

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

### 알람 감지

매 Polling 후 센서값 threshold 비교 → 위반 시 알람 키 SET, 복귀 시 DEL. **알람 검사는 제어 명령을 생성하지 않음** — UI 표시·이력 전용. 비상정지 연동은 TODO.

### 환경 센서

PCB를 거치지 않고 RPi에 직접 연결된 센서들. control_board가 자체 처리해 Redis에 SET.

- **온습도** — DHT11 또는 HDC302x 중 부팅 시 감지된 한쪽 사용 ([dlc_sensors.py:44-49](../exporter/dlc_sensors.py#L44-L49) 패턴) → `air_temp`, `air_humit`.
- **자이로** — MPU6050, dg5w 한정. 거의 필요없는 데이터지만 기존 sensor_exporter 호환을 위해 키 유지 → `chassis_stabil`. init/read graceful fallback ([dlc_sensors.py:52-59](../exporter/dlc_sensors.py#L52-L59), [:150-169](../exporter/dlc_sensors.py#L150-L169) 패턴) — 미장착·라이브러리 미설치·통신 실패 어떤 경우든 죽지 않고 stable=1로 fail-safe. dg5r은 키 자체 SET 안 함.

### 자동 제어 알고리즘

유량 센서 미장착이라 펌프 cascade 제어는 적용하지 않는다 — **펌프는 부팅 시 `config.yaml`로 초기 duty 한 번 Write 후 고정 운용**. controller.py는 팬 duty만 outlet 온도 lookup으로 갱신.

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

## Folder Layout

이번 단계에서는 디렉토리만 만들고 README만 둔다. 다음 단계에서 아래 모듈들이 들어올 예정:

```
src/control_board/
├── README.md                ← 본 문서
├── config.yaml              (예정) 초기 PWM duty, freq, threshold, slave_id, baud, serial port
├── main.py                  (예정) 엔트리포인트 — 메인 루프 기동, 공유 자원(redis/modbus) 보관
│
├── modbus_client.py         (예정) 단일 시리얼 버스 wrapper. probe(), read_input(), read_holding(), write_register(), write_coil(). 순차 실행 보장.
├── registers.py             (예정) PCB Modbus 레지스터 맵 상수 (HR/IR/Coil/Discrete 주소)
├── redis_keys.py            (예정) Redis 키 상수 모음 (기존 sensor 키 + 신규 알람/통신 키)
│
├── main_loop.py             (예정) 메인 루프 (Polling → 환경 센서 → Modbus Write)
│
├── polling.py               (예정) Modbus Read → 디코딩 → Redis SET + Pub/Sub
├── controller.py            (예정) outlet 온도 → 팬 duty lookup → Modbus Write. ±1 °C hysteresis. 펌프는 고정값 그대로.
├── alarm_checker.py         (예정) threshold 비교 → SET/DEL 알람 키 (제어 명령 생성 X)
│
├── env_sensors.py           (예정) 온습도 (DHT11/HDC302x 자동 감지) → air_temp·air_humit. 자이로 (MPU6050, dg5w 한정·거의 무의미) → chassis_stabil. init/read graceful fallback.
│
├── pcb_bootstrap.py         (예정) probe → systemctl start (control_board 또는 data_crawler)
└── requirements.txt         (예정) pymodbus, pyserial, redis, pyyaml, adafruit-circuitpython-dht, mpu6050-raspberrypi
```

systemd unit 파일 (예정, 위치는 기존 컨벤션 따름):

```
src/configure/daemons/gadgetini/
├── pcb_bootstrap.service    (예정) oneshot, multi-user.target에 wired
└── control_board.service    (예정) WantedBy 없음 (bootstrap이 직접 start). Restart=always.
```

기존 `data_crawler.service`는 `[Install] WantedBy=multi-user.target` 라인 제거 + `Conflicts=control_board.service` 추가만 적용 (Python 코드 무관).

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
