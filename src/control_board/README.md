# control_board

Gadgetini의 PCB 제어보드(MCS_IO Board) 통합 모듈. **MCG (Modbus Control Gateway)** 패턴을 따라 모니터링·Manual 제어·Auto 제어·알람 감지를 단일 게이트웨이 서비스로 통합한다.

설계의 통신 구조는 [DEEPGadget/L2A_CDU_system docs/MCG.md](https://github.com/DEEPGadget/L2A_CDU_system/blob/main/docs/MCG.md)를 따른다. 단, **센서 모델/수량/채널 매핑은 gadgetini(dg5r/dg5w) 별로 다르므로** 이 문서에는 적지 않는다 — 와이어링 도면 확정 후 별도 섹션으로 추가.

## Context

기존 gadgetini는 Raspberry Pi가 ADS1256 SPI ADC + I2C/GPIO로 센서를 직접 읽기만 하는 read-only 시스템이었다. ManyCoreSoft 자체 개발 **MCS_IO Board**(STM32G474, 절연 RS485 Modbus RTU)가 도입되면서:

1. **센서 경로 이전** — NTC 쿨란트 온도, 누수/레벨 입력이 ADS1256 → MCS_IO로 이동.
2. **신규 기능 — 자동 폐루프 제어** — Cooltron 팬(PWM 25 kHz, Tach), Koolance/Barrow 펌프(PWM 또는 전압 제어, Tach/Fault)를 센서값 기반 알고리즘으로 자동 제어 (dg5r/dg5w는 Manual 모드 없음 — Auto-only 운용).
3. **알람 감지** — threshold 기반 이상 감지 (제어 명령은 생성하지 않음, UI 표시 전용).

구버전 서버는 PCB 미장착이므로 **동일 image가 신/구 hw 모두에서 동작**해야 한다.

## Architecture

### 부팅 시 분기 (gadgetini 고유)

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
       │  = MCG Gateway    │   │                  │
       └─────────┬─────────┘   └────────┬─────────┘
                 │                      │
                 └──────► Redis ◄───────┘
```

`data_crawler.service`(구hw)와 `control_board.service`(신hw)는 **mutually exclusive**. `pcb_bootstrap.service`가 부팅 시 한 번만 결정하고 그 후 변경하지 않는다.

### control_board 내부 — MCG 패턴 (Auto-only 변형)

> **gadgetini(dg5r/dg5w)는 Manual 모드 없이 Auto만 운용한다.** L2A의 MCG는 UI 기반 Manual 제어를 지원하지만, 본 프로젝트의 dg5r/dg5w는 사람이 PWM을 직접 설정하는 흐름이 없다 → MCG 패턴에서 다음을 제거:
> - UI 수신 쓰레드 (제거) → 단일 메인 루프 쓰레드만 운용
> - command queue / Manual 제어 경로 (제거)
> - `control:mode` Redis key (사용 안 함)
> - bumpless transfer (Manual↔Auto 전환이 없으므로 불필요)
>
> 결과적으로 control_board는 **1 쓰레드 + 단순화된 메인 루프**가 된다. 향후 Manual 모드 도입이 필요해지면 ui_receiver / command_queue / manual_control 모듈을 추가하는 형태로 확장.

Modbus는 단일 시리얼 버스이므로 Read/Write가 동시에 일어날 수 없다. 모든 PCB 통신은 메인 루프 안에서 순차 실행한다.

### 메인 루프 (cycle 당)

```
1. Polling
     → Modbus Read (센서 + 현재 PWM duty)
     → 디코딩 → Redis SET sensor:* + Pub/Sub publish
     → 알람 threshold 검사 → SET/DEL alarm:*

2. RPi 직접 수집 센서 (DHT11/HDC302x 등)
     → SET sensor:ambient_*

3. Auto 알고리즘
     → 센서값 → PWM duty 결정
     → Modbus Write
```

> S-Curve 1초 ramping은 PCB 펌웨어가 자체 적용. 호스트는 raw target만 보내면 됨.
> Emergency 모드는 TODO (시스템 안정화 후 설계). 도입 시 step 0으로 "if Emergency: 전체 PWM=0, DOUT=0 후 skip" 추가.

### Redis Key Namespace (MCG.md §9, Auto-only 적용)

- `sensor:*` — 센서 현재값 (Polling이 SET)
- `alarm:*` — 이상 감지 (threshold 위반 시 SET, 복귀 시 DEL)
- `comm:*` — 통신 상태 (status / consecutive_failures / last_error)
- ~~`control:mode`~~ — 사용 안 함 (Auto-only)

> ⚠️ **기존 코드와의 namespace 충돌**: 현재 `sensor_exporter.py`는 flat key (`coolant_temp_inlet1` 등)를 읽는다. MCG는 `sensor:coolant_temp_inlet_1` namespace를 쓴다. 결정 필요:
> - (A) control_board가 두 키 모두 write — backward compat 유지, 단 zero-touch 거의 충족
> - (B) sensor_exporter를 prefix 인식하도록 패치 — 작은 수정
> - (C) 한 번에 새 namespace로 마이그레이션 — exporter/display/web 모두 갱신
>
> 와이어링 확정과 함께 결정.

### Prometheus 통합 (MCG.md §9)

- **Exporter** (Pull, 기존 `sensor_exporter.service`): `sensor:*`, `alarm:*` 주기 수집 → 시계열 적재
- **Pushgateway** (Push, control_board가 직접): 이벤트 발생 시 push
  - `comm_event` — 통신 상태 변경 시
  - (Manual 모드가 없으므로 `control_cmd_*`, `control_cmd_mode`는 미사용)

### 서비스 초기화 (MCG.md §7)

PCB 펌웨어에 초기값 Flash 저장이 미구현이므로, control_board 시작 시 `config.yaml`에서 로드한 값을 PCB에 Write:
- 팬 PWM 초기 duty
- 펌프 PWM 초기 duty
- TIM1/TIM2/(필요 시 TIM8) 주파수
- DOUT 초기 상태

`config.yaml`이 source of truth. systemd `Restart=always`로 전원 재인가 시 자동 재적용.

### 알람 감지 (MCG.md §8)

- 매 Polling 후 센서값 threshold 비교 → 위반 시 `alarm:*` SET, 복귀 시 DEL
- **알람 검사는 제어 명령을 생성하지 않음** — UI 표시·이력 전용
- 비상정지 연동은 TODO

### 환경 센서 (Modbus 미경유)

DHT11/HDC302x 같은 RPi I2C 직접 수집 센서는 PCB를 거치지 않고 control_board가 자체 처리해 `sensor:ambient_temp`, `sensor:ambient_humidity`로 SET. (MCG.md §9 "RPi 직접 수집"과 동일 패턴.)

## Folder Layout

이번 단계에서는 디렉토리만 만들고 README만 둔다. 다음 단계에서 아래 모듈들이 들어올 예정:

```
src/control_board/
├── README.md                ← 본 문서
├── config.yaml              (예정) 초기 PWM duty, freq, threshold, slave_id, baud, serial port
├── main.py                  (예정) 엔트리포인트 — 두 쓰레드 기동, 공유 자원(큐/redis/modbus) 보관
│
├── modbus_client.py         (예정) 단일 시리얼 버스 wrapper. probe(), read_input(), read_holding(), write_register(), write_coil(). 순차 실행 보장.
├── registers.py             (예정) MCS_IO 레지스터 맵 상수 (HR/IR/Coil/Discrete 주소)
├── redis_keys.py            (예정) sensor:*, alarm:*, comm:* 키 상수 모음
│
├── main_loop.py             (예정) 단일 메인 루프 (Polling → 환경 센서 → Auto Write)
│
├── polling.py               (예정) Modbus Read → 디코딩 → SET sensor:* + Pub/Sub
├── auto_control.py          (예정) 알고리즘 (sensor → PWM duty) → Modbus Write. Stage1 fan curve / Stage2 PI / Stage3 cascade 로드맵 (auto_control.md 참고). anti-windup, rate limit, hysteresis 가드레일.
├── alarm_checker.py         (예정) threshold 비교 → SET/DEL alarm:* (제어 명령 생성 X)
│
├── env_sensors.py           (예정) RPi I2C 직접 수집 (DHT11/HDC302x 등 — Modbus 미경유)
├── pushgateway.py           (예정) comm_event push helper
│
├── pcb_bootstrap.py         (예정) probe → systemctl start (control_board 또는 data_crawler)
└── requirements.txt         (예정) pymodbus, pyserial, redis, prometheus_client, pyyaml, adafruit-circuitpython-dht, mpu6050-raspberrypi
```

systemd unit 파일 (예정, 위치는 기존 컨벤션 따름):

```
src/configure/daemons/gadgetini/
├── pcb_bootstrap.service    (예정) oneshot, multi-user.target에 wired
└── control_board.service    (예정) WantedBy 없음 (bootstrap이 직접 start). Restart=always (MCG Watchdog 미구현 임시 대응).
```

기존 `data_crawler.service`는 `[Install] WantedBy=multi-user.target` 라인 제거 + `Conflicts=control_board.service` 추가만 적용 (Python 코드 무관).

## MCS_IO Board 통신 사양 요약

상세는 `MCS_BD_user_manual2.pdf` 및 `docs/PCB.md` 참조. 게이트웨이 코드 작성에 직접 영향 있는 항목만 발췌.

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

## 미구현 / 알려진 한계

- **PCB Watchdog 미구현** (PCB.md "미구현 기능") — control_board가 죽으면 PCB가 자체 안전 모드로 못 들어감. 임시 대응: systemd `Restart=always`.
- **PCB Flash 초기값 미저장** — 매 부팅 시 config.yaml에서 다시 Write 필요.
- **Emergency 모드 미설계** — 시스템 안정화 후 결정.
- **펌프 Fault 디코더 (Johnson eModule PWM 에러 패턴)** — TBD.
- **4-20 mA 센서 (유량/pH/전도도/유압)** — Voltage 채널(IR 32~39) 매핑 미정.

## 다음 단계

1. **CDU 변형별 와이어링 도면 확정** — 어느 PCB 채널/HR/IR/DIN/Pulse가 어느 액추에이터·센서에 연결되는지 (변형: dg5r / dg5w).
2. 와이어링 확정되면 본 README에 **§ 통신 구조 (변형별 매핑)** 섹션 추가 (Redis key ↔ Modbus register 표).
3. **Redis namespace 결정** (위 충돌 노트 참고) — A/B/C 중 선택.
4. **config.yaml 스키마 작성** — 초기 duty/freq, threshold 값, slave_id, baud, port.
5. 그 다음 모듈 코드 작성 시작 (`modbus_client.py` + `registers.py`부터).

## 참고 문서

- [DEEPGadget/L2A_CDU_system docs/MCG.md](https://github.com/DEEPGadget/L2A_CDU_system/blob/main/docs/MCG.md) — 본 게이트웨이의 통신 구조 원본
- `docs/PCB.md` (동 레포) — PCB 펌웨어 사양 (S-Curve, OCP/SCP/OTP, Watchdog 미구현 등)
- `docs/auto_control.md` (동 레포) — Auto 알고리즘 Stage 1/2/3 로드맵, 가드레일
- `docs/threshold.md` (동 레포) — 알람 threshold
- `MCS_BD_user_manual2.pdf` — MCS_IO Board 하드웨어 매뉴얼 (DIP, 레지스터 맵, CLI)
