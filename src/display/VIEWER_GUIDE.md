# Gadgetini Display System Guide

## 1. 시스템 개요

Raspberry Pi + ST7789 LCD (320×170px)에서 Redis 센서 데이터를 실시간 그래프로 표시하는 임베디드 디스플레이 시스템.

### 동작 흐름

```
display_main.py
  └─ DisplayManager
       ├─ config.ini 로드 → [PRODUCT], [DISPLAY] 설정 파싱
       ├─ profiles/<product>.py 로드 (동적 import)
       │    ├─ create_sensors(redis, config)  → dict[str, SensorData]
       │    └─ create_viewers(config)         → list[(config_key, Viewer)]
       │
       ├─ sensor_thread  → 각 SensorData.sensor_data_collector()  (1/FPS 주기)
       └─ graph_thread   → data_processor()
            ├─ sensor_data_processing()  → 큐 → 버퍼 적재
            ├─ history_store.accumulate() + tick()  → 10분 피크값 저장
            ├─ _check_leak()  → 누수 감지 시 LeakAlertViewer 활성화
            ├─ update_info()  → 5초마다 config.ini 리로드
            ├─ set_next_viewer()  → rotation_sec마다 뷰어 전환
            └─ draw_viewer(frame)  → 현재 뷰어의 draw() 호출 → LCD 출력
```

### 핵심 상수

| 상수 | 값 | 설명 |
|------|---|------|
| `GRAPH_SIZE` | 145 | 그래프/데이터 박스 한 변 (px) |
| `FPS` | 10 | 초당 프레임 수 |
| `max_points` | `GRAPH_SIZE - 5` = 140 | 센서 버퍼 최대 길이 |

---

## 2. 파일 구조

```
src/display/
├── display_main.py          # 진입점
├── display_manager.py       # 센서 수집, 뷰어 순환, 화면 출력 총괄
├── config.py                # 전역 상수 (DEBUG, GRAPH_SIZE, FPS, 폰트 경로, 하드웨어 import)
├── config.ini               # 런타임 설정 (제품, 뷰어 on/off, 방향 등)
│
├── sensor_data.py           # SensorData — Redis 읽기, 버퍼 관리, 색상 그라데이션
├── history_store.py         # HistoryStore — 24시간 히스토리 누적/저장/로드
│
├── base_viewer.py           # BaseViewer — 모든 뷰어의 부모 클래스
├── viewer.py                # SensorViewer — 단일 그래프 + 메인값 + 서브값
├── multi_viewer.py          # MultiSensorViewer — 멀티라인 그래프 + 값 목록
├── daily_viewer.py          # DailyViewer — 24시간 히스토리 그래프
├── dual_sensor_viewer.py    # DualSensorViewer — 독립 2패널 그래프
├── coolant_detail_viewer.py # CoolantDetailViewer — 쿨런트 루프 그래프 + ΔT
├── temp_util_viewer.py      # TempUtilViewer — 온도 + Util 듀얼 멀티그래프
├── leak_alert_viewer.py     # LeakAlertViewer — 누수 경고 전체화면 (특수, BaseViewer 미상속)
│
├── draw_utils.py            # 렌더링 유틸 (텍스트, 그래프, 폰트 캐시)
├── virtual_lcd.py           # 개발용 가상 LCD (OpenCV)
│
├── fonts/                   # JetBrains Mono 폰트 세트 + Nerd Font
│
└── profiles/
    ├── __init__.py           # load_product() — 동적 모듈 로딩
    ├── dg5r.py               # DG5R 제품 프로파일 (8 GPU, 2 CPU, 듀얼 쿨런트)
    └── dg5w.py               # DG5W 제품 프로파일 (단순 구성)
```

---

## 3. 핵심 클래스 상세

### 3.1 SensorData (`sensor_data.py`)

Redis에서 센서값을 읽어 버퍼에 축적하는 클래스.

```python
SensorData(
    title_str,      # 표시 이름 (예: "GPU0 Temp")
    unit_str,       # 단위 문자열 (예: "°C", "W", "%")
    min_val,        # 색상 그라데이션 최소값 (파란색)
    max_val,        # 색상 그라데이션 최대값 (빨간색)
    read_rate=1,    # 읽기 주기 (초 단위, 1=매초)
    redis=r,        # Redis 연결 객체
    redis_key=None,    # 단일 키 읽기
    redis_keys=None,   # 복수 키 중 max값 읽기
    formula=None,      # 커스텀 계산식 lambda r: ...
    icon=None,         # Nerd Font 유니코드 아이콘
    label=None,        # 짧은 라벨 (멀티뷰어 범례용)
)
```

**데이터 소스 (택 1, 우선순위 순):**

| 파라미터 | 동작 | 예시 |
|---------|------|------|
| `formula` | `lambda r: ...` 실행, `r`은 Redis 객체 | `lambda r: float(r.get('used_mem')) / float(r.get('total_mem')) * 100` |
| `redis_keys` | 리스트의 모든 키를 읽어 **최대값** 반환 | `[f"gpu_temp_{i}" for i in range(8)]` |
| `redis_key` | 단일 키에서 `float()` 변환 | `'coolant_temp_inlet1'` |
| _(없음)_ | 개발용 랜덤 데이터 생성 | — |

**주요 속성:**

| 속성 | 타입 | 설명 |
|------|------|------|
| `buffer` | `list[float]` | 최근 값 리스트 (최대 140개, 왼→오 시간순) |
| `error` | `bool` | 마지막 읽기 실패 여부 |
| `icon` | `str\|None` | Nerd Font 아이콘 유니코드 |
| `label` | `str\|None` | 짧은 라벨 (예: "G0", "IN1") |

**주요 메서드:**

| 메서드 | 설명 |
|--------|------|
| `sensor_data_collector()` | `read_rate`마다 Redis에서 값 읽어 큐에 넣음 |
| `sensor_data_processing()` | 큐 → 버퍼 이동 (max_points 초과 시 오래된 값 삭제) |
| `get_color_gradient(value)` | min↔max 기반 파란→빨간 RGB 튜플 반환 |

### 3.2 HistoryStore (`history_store.py`)

24시간 히스토리를 JSON 파일로 관리.

| 항목 | 값 |
|------|---|
| 저장 파일 | `history.json` (display_main.py 실행 디렉토리) |
| 저장 주기 | **10분마다** flush + 파일 저장 (atomic write via `.tmp` + `os.replace`) |
| 데이터 구조 | 10분간 수집된 샘플의 **최대값** 1개를 저장 |
| 최대 포인트 | 144개 (= 24h ÷ 10min) |
| 파일 포맷 | `{"sensor_key": [val, val, ...], ...}` |
| 그래프 정렬 | 왼쪽(과거) → 오른쪽(현재), 데이터 부족 시 왼쪽부터 채움 |

**동작 흐름:**
1. `DisplayManager.data_processor()`가 매초 `accumulate(key, value)` 호출
2. 10분 경과 시 `tick()` → `_flush()` (피크값 추출) → `save()` (파일 쓰기)
3. 프로그램 재시작 시 `load()`로 기존 히스토리 복원

### 3.3 DisplayManager (`display_manager.py`)

전체 시스템을 통합 관리하는 핵심 클래스.

**초기화 순서:**
1. `config.ini` 로드
2. Redis 연결
3. `profiles/<product>.py` 동적 import → `create_sensors()`, `create_viewers()` 호출
4. `config.ini`의 `[DISPLAY]` 키를 기반으로 활성 뷰어 필터링
5. `HistoryStore`, `LeakAlertViewer` 초기화
6. 센서 수집 스레드 + 화면 갱신 스레드 시작

**주요 속성 (뷰어에서 접근):**

| 속성 | 타입 | 설명 |
|------|------|------|
| `sensors` | `dict[str, SensorData]` | 전체 센서 딕셔너리 |
| `horizontal` | `int` | 1=가로, 0=세로 |
| `x_offset`, `y_offset` | `int` | LCD 표시 영역 오프셋 |
| `width`, `height` | `int` | 전체 화면 크기 |
| `ip_addr` | `str` | 현재 IP 주소 |
| `version` | `str` | 버전 문자열 (config.ini에서 로드) |
| `history_store` | `HistoryStore` | 24시간 히스토리 저장소 |

**런타임 동작:**
- 매 5초: `config.ini` 리로드 → 뷰어 on/off 반영, 방향 변경 적용
- 매 `rotation_sec`초: 다음 뷰어로 자동 전환
- 매 프레임: 누수 감지 확인 → 5초 연속 감지 시 `LeakAlertViewer` 활성화

---

## 4. 뷰어 클래스 가이드

### 4.1 BaseViewer (`base_viewer.py`)

모든 뷰어의 부모 클래스. 공통 렌더링 로직을 제공합니다.

#### 제공 메서드

| 메서드 | 시그니처 | 설명 |
|--------|---------|------|
| `_setup` | `(draw, disp_manager) → (x, y)` | 화면을 검은색으로 초기화하고, 디버그 테두리 그린 뒤 offset 튜플 반환 |
| `_boxes` | `(offset, horizontal) → (graphbox, databox)` | 표준 2박스 레이아웃 좌표 반환. 각각 `(x1, y1, x2, y2)` |
| `_draw_title` | `(draw, text, x, y, w, h=15)` | Bold 15pt, 흰색, 가운데 정렬, autoscale 적용 |
| `_draw_footer` | `(draw, dm, x, y, w, h=10, mode='both')` | IP(좌) + 버전(우) 표시. mode: `'both'`, `'left'`, `'right'` |
| `_normalize` | `(sensor_list, graph_h) → (min, max, norm_list)` | 복수 센서 공유 min/max로 정규화. 5% 마진 적용 |
| `_normalize_single` | `(sensor, graph_h, fixed_min, fixed_max) → (min, max, norm)` | 단일 센서 정규화. fixed 값 지정 가능 |
| `_draw_graph_labels` | `(draw, min, max, unit, gx, gy1, gy2, w, ...)` | 그래프 상단(max)/하단(min) 값 라벨 |
| `_draw_legend_row` | `(draw, sensor, label, color, cx, cy, row_h, col_w, sq=5)` | 색상 사각형 + 라벨 + 값 + 단위 한 줄 |
| `ERR_COLOR` | — | `(128, 128, 128)` 에러 표시 색상 |

#### 표준 2박스 레이아웃 (Horizontal 모드)

```
← GRAPH_SIZE=145 →  5px  ← GRAPH_SIZE=145 →
┌──────────────────┐     ┌──────────────────┐
│                  │     │                  │
│    Graph Box     │     │    Data Box      │
│    (145×145)     │     │    (145×145)     │
│                  │     │                  │
└──────────────────┘     └──────────────────┘
```

Vertical 모드에서는 위(Graph) + 아래(Data)로 배치됩니다.

### 4.2 SensorViewer (`viewer.py`)

단일 메인 센서 그래프 + 큰 값 표시 + 서브 센서 1~2개.

```python
SensorViewer(
    title,                  # 타이틀 (예: "MEM Info")
    sensor_key,             # 메인 센서 키
    sub1_key=None,          # 서브 센서 1 (선택)
    sub2_key=None,          # 서브 센서 2 (선택)
    fixed_min=None,         # 그래프 Y축 최소 고정값
    fixed_max=None,         # 그래프 Y축 최대 고정값
    sub1_autoscale=False,   # 서브1 폰트 자동축소
    sub2_autoscale=False,   # 서브2 폰트 자동축소
)
```

**레이아웃 (Data Box):**

```
┌─────────────────────┐
│     Title (30px)    │
│  값  50.2  °C       │  ← 메인값 50pt + 단위 40pt
│                     │
│  ┌─sub1──┐┌─sub2──┐│  ← 서브 2개일 때 좌/우 분할
│  │ 󰔏 USED││ 󰔏 FREE││    아이콘/라벨 + 값 + 단위
│  │ 512.3 ││ 256.1 ││
│  └───────┘└───────┘│
│ IP           ver    │  ← 푸터 12px
└─────────────────────┘
```

서브 1개일 때는 전체 너비를 사용하여 큰 폰트(36pt)로 표시.

**그래프:** 단일 센서의 gradient fill + glow + main line. 값에 따른 파란↔빨간 색상 그라데이션.

**사용 예 (dg5r.py):**
```python
("memory", SensorViewer("MEM Info",
    sensor_key="mem_util",
    sub1_key="mem_used", sub2_key="mem_free",
    fixed_min=0, fixed_max=100,
    sub1_autoscale=True, sub2_autoscale=True))
```

### 4.3 MultiSensorViewer (`multi_viewer.py`)

여러 센서를 하나의 멀티라인 그래프에 겹쳐 표시 + 값 목록.

```python
MultiSensorViewer(
    title,          # 타이틀
    sensor_keys,    # 센서 키 리스트
    colors,         # RGB 색상 리스트 (센서별)
    labels,         # 짧은 라벨 리스트
)
```

**레이아웃 (Data Box):**

```
┌─────────────────────┐
│     Title (25px)    │
│ ■ IN1   32.5 °C    │  ← 센서 ≤5개: 1열
│ ■ OUT1  35.2 °C    │
│ ■ IN2   31.8 °C    │
│ ■ OUT2  34.1 °C    │
│ IP           ver    │
└─────────────────────┘
```

센서 6개 이상일 때 자동으로 2열 레이아웃으로 전환되며, 폰트 크기도 자동 축소됩니다.

**폰트 적응형 크기:**

| 조건 | 값 폰트 | 라벨 폰트 |
|------|---------|----------|
| 1열, row_h ≥ 24px | 20pt | 10pt |
| 1열, row_h ≥ 18px | 14pt | 8pt |
| 2열 | 14pt (최대) | 8pt |
| 작은 행 | 10pt | 7pt |

**그래프:** 공유 스케일 멀티라인 (glow 3px + main line 2px). gradient fill 없음.

**사용 예 (dg5r.py):**
```python
("coolant", MultiSensorViewer("Coolant Overview",
    sensor_keys=["coolant_inlet1", "coolant_outlet1",
                 "coolant_inlet2", "coolant_outlet2"],
    colors=[(0, 200, 255), (255, 140, 0),
            (0, 220, 100), (255, 50, 200)],
    labels=["IN1", "OUT1", "IN2", "OUT2"]))
```

### 4.4 DualSensorViewer (`dual_sensor_viewer.py`)

독립적인 2개의 단일 센서 그래프를 좌/우(또는 상/하)로 나란히 표시.

```python
DualSensorViewer(
    panels=[
        {"title": "패널1 제목", "sensor_key": "센서키1"},
        {"title": "패널2 제목", "sensor_key": "센서키2"},
    ]
)
```

**레이아웃 (Horizontal):**

```
┌── Panel 0 (145px) ──┐  5px  ┌── Panel 1 (145px) ──┐
│     Title (15px)     │       │     Title (15px)     │
│                      │       │                      │
│   Graph (90px)       │       │   Graph (90px)       │
│   gradient fill      │       │   gradient fill      │
│                      │       │                      │
│    32.5 °C (30px)    │       │    65.2 % (30px)     │
│ IP                   │       │              ver     │
└──────────────────────┘       └──────────────────────┘
```

각 패널은 독립적인 스케일로 정규화됩니다. 푸터는 좌측 패널에 IP, 우측 패널에 version을 나눠 표시합니다.

**사용 예 (dg5r.py):**
```python
("chassis", DualSensorViewer(panels=[
    {"title": "Air Temperature", "sensor_key": "chassis_temp"},
    {"title": "Humidity", "sensor_key": "chassis_humid"},
]))
```

### 4.5 CoolantDetailViewer (`coolant_detail_viewer.py`)

쿨런트 루프별 상세 뷰어. 각 루프의 Inlet/Outlet 멀티그래프 + 개별 값 + ΔT.

```python
CoolantDetailViewer(
    loops=[
        {
            "title": "Loop 1",
            "sensor_keys": ["coolant_inlet1", "coolant_outlet1"],
            "delta_key": "coolant_delta1",
            "colors": [(0, 200, 255), (255, 140, 0)],
            "labels": ["IN1", "OUT1"],
        },
        # ... 추가 루프
    ]
)
```

**레이아웃 (패널 1개):**

```
┌──────────────────────┐
│     Loop 1 (15px)    │  ← 타이틀
│                      │
│  Multi Graph (78px)  │  ← IN/OUT 2라인 공유 스케일
│                      │
│ ■ IN1   32.5 °C     │  ← 값 행 (15px × 2)
│ ■ OUT1  35.2 °C     │
│   ΔT 2.7°C (12px)   │  ← 델타T
│ IP           ver     │  ← 푸터 10px
└──────────────────────┘
```

**사용 예 (dg5r.py):**
```python
("coolant_detail", CoolantDetailViewer(loops=[
    {"title": "Loop 1",
     "sensor_keys": ["coolant_inlet1", "coolant_outlet1"],
     "delta_key": "coolant_delta1",
     "colors": [(0, 200, 255), (255, 140, 0)],
     "labels": ["IN1", "OUT1"]},
    {"title": "Loop 2",
     "sensor_keys": ["coolant_inlet2", "coolant_outlet2"],
     "delta_key": "coolant_delta2",
     "colors": [(0, 220, 100), (255, 50, 200)],
     "labels": ["IN2", "OUT2"]},
]))
```

### 4.6 TempUtilViewer (`temp_util_viewer.py`)

좌측: 온도 멀티그래프, 우측: 유틸/파워 멀티그래프, 하단: 공유 범례.

```python
TempUtilViewer(
    temp_title,     # 좌측 그래프 타이틀 (예: "GPU Temperature")
    util_title,     # 우측 그래프 타이틀 (예: "GPU Power")
    sensor_keys,    # 온도 센서 키 리스트
    colors,         # RGB 색상 리스트 (양쪽 그래프 공유)
    labels,         # 범례 라벨 리스트
    util_keys,      # 유틸/파워 센서 키 리스트 (개별)
)
```

**레이아웃 (Horizontal):**

```
┌─ Temp Graph (145px) ─┐ 5px ┌─ Util Graph (145px) ─┐
│  "GPU Temperature"   │     │  "GPU Power"          │  ← 타이틀 12px
│                      │     │                       │
│  8-line multi graph  │     │  8-line multi graph   │  ← 그래프 95px
│  (공유 스케일)        │     │  (공유 스케일)         │
│                      │     │                       │
├──────────────────────┴─────┴───────────────────────┤
│ ■G0 72.5°C  ■G1 68.3°C  ■G2 70.1°C  ■G3 69.8°C  │  ← 범례
│ ■G4 71.2°C  ■G5 67.9°C  ■G6 73.0°C  ■G7 69.5°C  │    (전체 너비)
├────────────────────────────────────────────────────┤
│ IP                                          ver    │  ← 푸터 10px
└────────────────────────────────────────────────────┘
```

범례는 센서 ≤4개면 1행, 5~8개면 2행(4열)으로 표시됩니다.

**사용 예 (dg5r.py):**
```python
("gpu", TempUtilViewer(
    temp_title="GPU Temperature",
    util_title="GPU Power",
    sensor_keys=[f"gpu{i}_temp" for i in range(gpu_count)],
    colors=GPU_COLORS[:gpu_count],
    labels=[f"G{i}" for i in range(gpu_count)],
    util_keys=[f"gpu{i}_power" for i in range(gpu_count)]))
```

### 4.7 DailyViewer (`daily_viewer.py`)

24시간 히스토리 데이터를 멀티라인 그래프로 표시. 데이터 패널은 현재 실시간 값을 보여줍니다.

```python
DailyViewer(
    title,          # 타이틀 (예: "Coolant 24h")
    sensor_keys,    # 센서 키 리스트
    colors,         # RGB 색상 리스트
    labels,         # 짧은 라벨 리스트
)
```

**그래프 특징:**
- 데이터 소스: `HistoryStore`의 10분 피크값 (최대 144포인트)
- 왼쪽(과거) → 오른쪽(현재) 정렬, 데이터 부족 시 왼쪽부터 채움
- 수직 시간 마커: 6h, 12h, 18h 전 위치에 점선 표시
- 수평 그리드: 25%, 50%, 75% 위치에 점선

데이터 패널 레이아웃은 MultiSensorViewer와 동일합니다 (적응형 열/폰트).

**히스토리가 아직 없고 실시간 데이터만 있을 때:** 그래프 중앙에 현재 피크값 텍스트 + 가로 점선만 표시.

**사용 예 (dg5r.py):**
```python
("coolant_daily", DailyViewer("Coolant 24h",
    sensor_keys=["coolant_inlet1", "coolant_outlet1",
                 "coolant_inlet2", "coolant_outlet2"],
    colors=[(0, 200, 255), (255, 140, 0),
            (0, 220, 100), (255, 50, 200)],
    labels=["IN1", "OUT1", "IN2", "OUT2"]))
```

### 4.8 LeakAlertViewer (`leak_alert_viewer.py`)

누수 감지 시 활성화되는 전체화면 경고. **BaseViewer를 상속하지 않는** 특수 뷰어.

- 1Hz 깜빡임: 빨간 배경 + 흰 글자 ↔ 검은 배경 + 빨간 글자
- "WARNING" (60pt) + "COOLANT LEAK DETECTED" (14pt)
- 일반 뷰어 순환을 무시하고 항상 최상위 표시
- `config.ini`의 `leak=on` + Redis `coolant_leak` 키가 5초 연속 1일 때 활성화

---

## 5. 렌더링 유틸 (`draw_utils.py`)

### 5.1 `draw_aligned_text()`

박스 안에 텍스트를 정렬하여 그리는 핵심 함수.

```python
draw_aligned_text(
    draw,               # PIL ImageDraw 객체
    text,               # 표시할 문자열
    font_size,          # 기본 폰트 크기
    fill,               # 색상
    box=(x, y, w, h),   # 렌더링 영역
    align="left",       # 수평 정렬: "left" | "center" | "right"
    halign="top",       # 수직 정렬: "top" | "center" | "bottom"
    font_path=FONT_PATH,
    autoscale=False,    # True면 박스에 맞춰 폰트 축소
    ref_text=None,      # autoscale 기준 문자열 (지터 방지용)
)
```

**`ref_text` 파라미터:** autoscale 시 실제 텍스트 대신 고정 문자열(예: `"000.0"`)로 폰트 크기를 계산하여 값 변동에 따른 글자 크기 흔들림(jitter)을 방지합니다.

**DEBUG 모드:** `DEBUG != 0`이면 빨간 박스(영역) + 초록 박스(실제 텍스트 바운딩) 표시.

### 5.2 그래프 함수

| 함수 | 용도 | 스타일 |
|------|------|--------|
| `draw_graph()` | 단일 센서 (SensorViewer, DualSensorViewer) | gradient fill + glow(5px) + main(2px) |
| `draw_multi_graph()` | 멀티 센서 실시간 (MultiSensorViewer 등) | glow(3px) + main(2px), fill 없음 |
| `draw_daily_graph()` | 24시간 히스토리 (DailyViewer) | glow(3px) + main(2px) + 시간 마커 |

**공통 요소:**
- 수평 그리드 점선: 25%, 50%, 75% 위치
- 그래프 영역: `(x1, y1, x2, y2)` 튜플로 지정

### 5.3 폰트 캐시

`get_cached_font(size, font_path)` — 동일 (size, path) 조합은 한 번만 로드하여 캐시.

**사용 가능한 폰트:**

| 변수 | 파일 | 용도 |
|------|------|------|
| `FONT_PATH` | JetBrainsMono-Regular | 라벨, 단위 |
| `BOLD_FONT_PATH` | JetBrainsMono-Bold | 타이틀, 값 표시 |
| `EXTRABOLD_FONT_PATH` | JetBrainsMono-ExtraBold | 메인 큰 값 |
| `LIGHT_FONT_PATH` | JetBrainsMono-Light | 푸터 |
| `THIN_FONT_PATH` | JetBrainsMono-Thin | 작은 서브 라벨 |
| `ICON_FONT_PATH` | JetBrainsMonoNerdFont-Bold | Nerd Font 아이콘 |

---

## 6. config.ini 레퍼런스

```ini
[PRODUCT]
name=dg5r              # 프로파일 이름 (profiles/ 폴더에서 동적 로드)
version=gadgetini v0.35
redis_host=localhost
redis_port=6379
gpu_count=8            # GPU 수 (프로파일에서 동적 센서 생성에 사용)
cpu_count=2            # CPU 수

[DISPLAY]
orientation=horizontal  # horizontal | vertical
display=on              # off면 화면 끔 (검은 화면)
rotation_sec=8          # 뷰어 자동 전환 간격 (초)
leak=on                 # 누수 감지 활성화

# 뷰어 활성화 (키 = create_viewers()의 첫번째 값)
coolant=on              # MultiSensorViewer — 쿨런트 4센서 오버뷰
coolant_detail=on       # CoolantDetailViewer — 쿨런트 루프별 상세
chassis=on              # DualSensorViewer — 주변 온도 + 습도
gpu=on                  # TempUtilViewer — GPU 온도 + 파워
cpu=on                  # TempUtilViewer — CPU 온도 + 유틸
memory=on               # SensorViewer — 메모리 사용률 + Used/Free
coolant_daily=on        # DailyViewer — 쿨런트 24시간
gpu_daily=on            # DailyViewer — GPU 온도 24시간
cpu_daily=on            # DailyViewer — CPU 온도 24시간
```

뷰어 키를 `off`로 설정하면 해당 뷰어를 순환 목록에서 제외합니다.
config.ini는 **5초마다 자동 리로드**되므로, 실행 중 파일을 수정하면 즉시 반영됩니다.

---

## 7. 프로파일 구조 (`profiles/`)

### 필수 함수

프로파일 모듈은 다음 4개 함수를 반드시 export 해야 합니다:

```python
def create_sensors(redis, config=None) -> dict[str, SensorData]:
    """전체 센서 딕셔너리 반환."""

def create_viewers(config=None) -> list[tuple[str, Viewer]]:
    """(config_key, viewer_instance) 튜플 리스트 반환."""

def create_fallback_sensors(redis) -> dict[str, SensorData]:
    """센서 초기화 실패 시 최소한의 안전 센서셋."""

def create_fallback_viewers() -> list[tuple[str, Viewer]]:
    """센서 초기화 실패 시 표시할 안전 뷰어."""
```

### DG5R 센서 목록

| 키 | 이름 | 단위 | Redis 소스 |
|---|------|------|-----------|
| `coolant_inlet1` | Coolant Inlet1 | °C | `coolant_temp_inlet1` |
| `coolant_outlet1` | Coolant Outlet1 | °C | `coolant_temp_outlet1` |
| `coolant_delta1` | Coolant ΔT1 | °C | `coolant_delta_t1` |
| `coolant_inlet2` | Coolant Inlet2 | °C | `coolant_temp_inlet2` |
| `coolant_outlet2` | Coolant Outlet2 | °C | `coolant_temp_outlet2` |
| `coolant_delta2` | Coolant ΔT2 | °C | `coolant_delta_t2` |
| `chassis_temp` | Air Temperature | °C | `air_temp` |
| `chassis_humid` | Chassis Humidity | % | `air_humit` |
| `gpu{0-7}_temp` | GPU{i} Temp | °C | `gpu{i}_gpu_temp` |
| `gpu{0-7}_power` | GPU{i} Power | W | `gpu{i}_gpu_power` |
| `cpu{0-1}_temp` | CPU{i} Temperature | °C | `cpu_{i}_temp` |
| `cpu{0-1}_util` | CPU{i} Utilization | % | `cpu_{i}_util` |
| `mem_util` | Memory Utilization | % | formula: `used_mem / total_mem * 100` |
| `mem_used` | Used Memory | GB | `used_mem` |
| `mem_free` | Free Memory | GB | `avail_mem` |

### DG5R 뷰어 목록

| config 키 | 뷰어 클래스 | 설명 |
|----------|------------|------|
| `coolant` | MultiSensorViewer | IN1/OUT1/IN2/OUT2 4라인 그래프 |
| `coolant_detail` | CoolantDetailViewer | Loop1/Loop2 상세 + ΔT |
| `chassis` | DualSensorViewer | 주변 온도 + 습도 |
| `gpu` | TempUtilViewer | 8 GPU 온도 + 8 GPU 파워 |
| `cpu` | TempUtilViewer | 2 CPU 온도 + 2 CPU 유틸 |
| `memory` | SensorViewer | 메모리 % + Used + Free |
| `coolant_daily` | DailyViewer | 쿨런트 24시간 |
| `gpu_daily` | DailyViewer | GPU 온도 24시간 |
| `cpu_daily` | DailyViewer | CPU 온도 24시간 |

---

## 8. How-To

### 8.1 센서 추가하기

**1단계:** `profiles/<product>.py`의 `create_sensors()`에 항목 추가

```python
"my_sensor": SensorData(
    "My Sensor",          # 표시 이름
    "°C",                 # 단위
    0, 100,               # 그라데이션 min/max
    read_rate=1,          # 읽기 주기 (초)
    redis=r,
    redis_key='my_redis_key',
    icon="\U000f0510",    # 선택: Nerd Font 아이콘
    label="MY",           # 선택: 짧은 라벨
),
```

**2단계:** 뷰어 생성자에서 해당 센서 키를 참조

### 8.2 뷰어 추가하기

**1단계:** 용도에 맞는 뷰어 클래스 선택 (4장 참고)

**2단계:** `profiles/<product>.py`의 `create_viewers()`에 튜플 추가

```python
("my_viewer", MultiSensorViewer(
    "My Title",
    sensor_keys=["sensor_a", "sensor_b"],
    colors=[(255, 0, 0), (0, 255, 0)],
    labels=["A", "B"])),
```

**3단계:** `config.ini`의 `[DISPLAY]`에 활성화 키 추가

```ini
my_viewer=on
```

### 8.3 센서 삭제하기

1. `profiles/<product>.py`의 `create_sensors()` 딕셔너리에서 해당 항목 제거
2. 해당 센서를 참조하는 **모든 뷰어**의 `sensor_keys`, `sub1_key` 등에서 제거
3. 필요 시 `create_fallback_sensors()`에서도 제거

### 8.4 뷰어 삭제하기

1. `profiles/<product>.py`의 `create_viewers()` 리스트에서 해당 튜플 제거
2. `config.ini`의 `[DISPLAY]`에서 해당 키 제거
3. 해당 뷰어만 사용하던 센서가 있으면 함께 정리

### 8.5 새 뷰어 클래스 만들기

`BaseViewer`를 상속하여 `draw()` 메서드를 구현합니다.

```python
from base_viewer import BaseViewer
from config import GRAPH_SIZE
from draw_utils import draw_aligned_text, draw_multi_graph

class MyViewer(BaseViewer):
    def __init__(self, title, sensor_keys, colors, labels):
        super().__init__()        # self.active = 1 자동 설정
        self.title = title
        self.sensor_keys = sensor_keys
        self.colors = colors
        self.labels = labels

    def draw(self, draw, disp_manager, frame):
        # 1. 화면 초기화 + offset
        offset = self._setup(draw, disp_manager)

        # 2. 표준 2-box 레이아웃
        graphbox, databox = self._boxes(offset, disp_manager.horizontal)
        gx1, gy1, gx2, gy2 = graphbox
        dx1, dy1, dx2, dy2 = databox

        # 3. 센서 데이터 가져오기
        sensors = [disp_manager.sensors[k] for k in self.sensor_keys]
        has_data = any(len(s.buffer) >= 2 for s in sensors)
        if not has_data:
            return

        # 4. 타이틀
        dw = dx2 - dx1
        self._draw_title(draw, self.title, dx1, dy1, dw, h=25)

        # 5. 그래프 정규화 + 렌더링
        min_val, max_val, norm_list = self._normalize(sensors, GRAPH_SIZE)
        self._draw_graph_labels(draw, min_val, max_val,
                                sensors[0].unit_str,
                                gx1, gy1, gy2, GRAPH_SIZE)
        draw_multi_graph(draw, sensors, norm_list, self.colors, graphbox)

        # 6. 데이터 패널 (커스텀 렌더링)
        # ... 값 표시, 범례 등 ...

        # 7. 푸터
        self._draw_footer(draw, disp_manager, dx1, dy2 - 12, GRAPH_SIZE, h=12)
```

**draw() 메서드 규약:**
- 매개변수: `(self, draw, disp_manager, frame)`
  - `draw`: PIL `ImageDraw` 객체
  - `disp_manager`: `DisplayManager` 인스턴스 (sensors, horizontal, ip_addr 등 접근)
  - `frame`: 현재 프레임 번호 (0~FPS-1, 애니메이션용)
- 데이터가 없으면 조기 return (빈 화면 유지)

### 8.6 새 제품 프로파일 만들기

1. `profiles/my_product.py` 파일 생성
2. 4개 필수 함수 구현 (7장 참고)
3. `config.ini`의 `[PRODUCT]` 섹션에서 `name=my_product` 설정

### 8.7 개발/디버그 모드

`config.py`의 플래그를 변경:

| 플래그 | 값 | 효과 |
|-------|---|------|
| `DEBUG` | `1` | 모든 박스에 파란/빨간/초록 테두리 표시 |
| `USE_VIRTUAL_LCD` | `True` | OpenCV 창으로 출력 (실제 LCD 불필요) |
| `USE_REAL_DATA` | `False` | Redis 없이 랜덤 데이터로 동작 |

---

## 9. 자주 쓰는 Nerd Font 아이콘

| 아이콘 | 유니코드 | 용도 |
|--------|---------|------|
| 󰔐 | `\U000f0510` | 온도 |
| 󰖎 | `\U000f058e` | 습도 |
| 󰐥 | `\U000f0ee0` | CPU |
| 󰍛 | `\U000f035b` | 메모리 |
| 󰐋 | `\U000f140b` | 전력 |

---

## 10. 실행

```bash
cd ~/gadgetini/src/display
python3 display_main.py
```

가상 LCD 모드 (개발):
```python
# config.py 수정
USE_VIRTUAL_LCD = True
USE_REAL_DATA = False
```
