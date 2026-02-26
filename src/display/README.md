# Gadgetini Display System

Raspberry Pi 4 B+에서 ST7789 TFT LCD(320×170px)를 통해 Redis 센서 데이터를 실시간 그래프로 표시하는 임베디드 디스플레이 시스템입니다.

---

## 목차

1. [전체 구조](#1-전체-구조)
2. [파일 구조](#2-파일-구조)
3. [핵심 개념](#3-핵심-개념)
4. [뷰어(Viewer) 가이드](#4-뷰어viewer-가이드)
5. [프로파일(Profile) 가이드](#5-프로파일profile-가이드)
6. [config.ini 레퍼런스](#6-configini-레퍼런스)
7. [개발 모드](#7-개발-모드)

---

## 1. 전체 구조

### 동작 흐름

```
display_main.py
  └─ DisplayManager
       ├─ config.ini 로드 → [PRODUCT], [DISPLAY] 파싱
       ├─ profiles/<product>.py 동적 import
       │    ├─ create_sensors(redis, config) → dict[str, SensorData]
       │    └─ create_viewers(config)        → list[(config_key, Viewer)]
       │
       ├─ sensor_thread  → SensorData.sensor_data_collector()   (1/FPS 주기)
       └─ graph_thread   → data_processor()
            ├─ sensor_data_processing()   큐 → 버퍼 적재
            ├─ history_store.accumulate() 10분 피크값 누적
            ├─ _check_leak()              누수 감지 시 LeakAlertViewer 활성화
            ├─ update_info()              5초마다 config.ini 리로드
            ├─ set_next_viewer()          rotation_sec마다 뷰어 전환
            └─ draw_viewer(frame)         현재 뷰어 draw() 호출 → LCD 출력
```

### 레이아웃 좌표계

화면은 `GRAPH_SIZE`(145px) 단위의 2-box 구조를 기본으로 합니다.

```
Horizontal 모드 (320×170):
← GRAPH_SIZE=145 →  5px  ← GRAPH_SIZE=145 →
┌──────────────────┐     ┌──────────────────┐
│                  │     │                  │
│    Graph Box     │     │    Data Box      │
│    (145×145)     │     │    (145×145)     │
│                  │     │                  │
└──────────────────┘     └──────────────────┘

Vertical 모드 (170×320):
위 = Graph Box, 아래 = Data Box
```

### 주요 상수 (`config.py`)

| 상수 | 값 | 설명 |
|------|---|------|
| `GRAPH_SIZE` | 145 | 그래프/데이터 박스 한 변 (px) |
| `FPS` | 15 | 초당 프레임 수 |
| `max_points` | 140 | 센서 버퍼 최대 길이 (GRAPH_SIZE - 5) |

---

## 2. 파일 구조

```
src/display/
├── display_main.py           진입점 — DisplayManager 실행
├── display_manager.py        센서 수집·뷰어 순환·화면 출력 총괄
├── config.py                 전역 상수 (DEBUG, GRAPH_SIZE, FPS, 폰트 경로, 하드웨어 import)
├── config.ini                런타임 설정 (제품명, 뷰어 on/off, 방향, Redis 접속 등)
│
├── sensor_data.py            SensorData — Redis 읽기, 버퍼 관리, 색상 그라데이션
├── history_store.py          HistoryStore — 24시간 히스토리 누적/저장/복원
├── profile_loader.py         JSON 프로파일 파서 (load_sensors, load_viewers)
│
├── base_viewer.py            BaseViewer — 모든 뷰어의 부모 클래스
├── viewer.py                 SensorViewer — 단일 그래프 + 메인값 + 서브값 1~2개
├── multi_viewer.py           MultiSensorViewer — 멀티라인 그래프 + 값 목록
├── daily_viewer.py           DailyViewer — 24시간 히스토리 그래프
├── dual_sensor_viewer.py     DualSensorViewer — 독립 2패널 그래프
├── coolant_detail_viewer.py  CoolantDetailViewer — 쿨런트 루프 그래프 + ΔT
├── temp_util_viewer.py       TempUtilViewer — 온도 + 유틸/파워 듀얼 멀티그래프
├── leak_alert_viewer.py      LeakAlertViewer — 누수 경고 전체화면 (특수)
│
├── draw_utils.py             렌더링 유틸 (텍스트 정렬, 그래프 함수, 폰트 캐시)
├── virtual_lcd.py            개발용 가상 LCD (OpenCV 창)
│
├── fonts/                    JetBrains Mono 폰트 세트 + Nerd Font
│
└── profiles/
    ├── __init__.py           load_product() — 동적 모듈 로딩
    ├── dg5r.py               DG5R 제품 프로파일 (JSON 방식)
    ├── dg5r.json             DG5R 센서/뷰어 정의 (JSON)
    ├── dg5r_default.json     DG5R 기본 설정 백업
    └── dg5w.py               DG5W 제품 프로파일 (Python 방식, 레거시)
```

---

## 3. 핵심 개념

### SensorData

Redis에서 센서값을 읽어 버퍼에 축적하는 클래스입니다.

```python
SensorData(
    title_str,          # 표시 이름 (예: "GPU0 Temp")
    unit_str,           # 단위 (예: "°C", "W", "%")
    min_val,            # 색상 그라데이션 하한값 (파란색)
    max_val,            # 색상 그라데이션 상한값 (빨간색)
    read_rate=1,        # 읽기 주기 (초, 기본 1)
    redis=r,
    redis_key=None,     # 단일 Redis 키 읽기
    redis_keys=None,    # 복수 키 중 최대값 읽기
    formula=None,       # 커스텀 계산식 lambda r: ...
    icon=None,          # Nerd Font 아이콘 (유니코드)
    label=None,         # 짧은 라벨 (예: "G0", "IN1")
    host_data=0,        # 1이면 host 연결 시에만 표시
)
```

**데이터 소스 우선순위:** `formula` > `redis_keys` (최대값) > `redis_key` (단일값)

### 뷰어 등록 흐름

```
config.ini [PRODUCT] name=dg5r
    → profiles/__init__.py: load_product("dg5r")
        → profiles/dg5r.py: create_sensors(), create_viewers()
            → profile_loader.py: load_sensors(dg5r.json), load_viewers(dg5r.json)
```

JSON 프로파일(`.json`)을 사용하는 경우 `profile_loader.py`의 `VIEWER_CLASSES` 딕셔너리에 등록된 클래스만 사용할 수 있습니다.

```python
# profile_loader.py
VIEWER_CLASSES = {
    "SensorViewer": SensorViewer,
    "MultiSensorViewer": MultiSensorViewer,
    "DailyViewer": DailyViewer,
    "DualSensorViewer": DualSensorViewer,
    "CoolantDetailViewer": CoolantDetailViewer,
    "TempUtilViewer": TempUtilViewer,
}
```

---

## 4. 뷰어(Viewer) 가이드

### 4.1 내장 뷰어 클래스

| 클래스 | 파일 | 용도 |
|--------|------|------|
| `SensorViewer` | viewer.py | 단일 그래프 + 큰 값 표시 + 서브 센서 1~2개 |
| `MultiSensorViewer` | multi_viewer.py | 멀티라인 그래프 + 값 목록 |
| `DualSensorViewer` | dual_sensor_viewer.py | 독립 2패널 그래프 |
| `CoolantDetailViewer` | coolant_detail_viewer.py | 쿨런트 루프 그래프 + ΔT |
| `TempUtilViewer` | temp_util_viewer.py | 온도 + 유틸/파워 듀얼 그래프 + 범례 |
| `DailyViewer` | daily_viewer.py | 24시간 히스토리 멀티라인 그래프 |

**각 뷰어의 생성자 파라미터:**

<details>
<summary>SensorViewer</summary>

```python
SensorViewer(
    title,                # 타이틀
    sensor_key,           # 메인 센서 키 (그래프 + 큰 값)
    sub1_key=None,        # 서브 센서 1 키 (선택)
    sub2_key=None,        # 서브 센서 2 키 (선택)
    fixed_min=None,       # Y축 최소 고정값 (None이면 자동)
    fixed_max=None,       # Y축 최대 고정값 (None이면 자동)
    sub1_autoscale=False, # 서브1 값 폰트 자동 축소 여부
    sub2_autoscale=False, # 서브2 값 폰트 자동 축소 여부
)
```
</details>

<details>
<summary>MultiSensorViewer</summary>

```python
MultiSensorViewer(
    title,        # 타이틀
    sensor_keys,  # 센서 키 리스트
    colors,       # RGB 색상 리스트 [(R,G,B), ...]
    labels,       # 짧은 라벨 리스트
)
```
</details>

<details>
<summary>DualSensorViewer</summary>

```python
DualSensorViewer(
    panels=[
        {"title": "패널1 제목", "sensor_key": "센서키1"},
        {"title": "패널2 제목", "sensor_key": "센서키2"},
    ],
    status_badges=[           # 선택: 상태 표시 배지
        {
            "key": "coolant_level",
            "label": "LEVEL",
            "ok_value": 1,    # 정상 값
            "ok_text": "OK",
            "alert_text": "LOW!",
        },
    ],
)
```
</details>

<details>
<summary>CoolantDetailViewer</summary>

```python
CoolantDetailViewer(
    loops=[
        {
            "title": "Loop 1",
            "sensor_keys": ["inlet_key", "outlet_key"],
            "delta_key": "delta_key",
            "colors": [(R,G,B), (R,G,B)],
            "labels": ["IN1", "OUT1"],
        },
    ],
)
```
</details>

<details>
<summary>TempUtilViewer</summary>

```python
TempUtilViewer(
    temp_title,    # 좌측 그래프 타이틀
    util_title,    # 우측 그래프 타이틀
    sensor_keys,   # 온도 센서 키 리스트
    colors,        # RGB 색상 리스트 (양쪽 공유)
    labels,        # 범례 라벨 리스트
    util_keys,     # 유틸/파워 센서 키 리스트
)
```
</details>

<details>
<summary>DailyViewer</summary>

```python
DailyViewer(
    title,        # 타이틀 (예: "Coolant 24h")
    sensor_keys,  # 센서 키 리스트
    colors,       # RGB 색상 리스트
    labels,       # 짧은 라벨 리스트
)
```
</details>

---

### 4.2 뷰어 추가

**방법 A — JSON 프로파일 수정 (권장: dg5r 계열)**

1. `profiles/<product>.json`의 `"viewers"` 배열에 항목 추가

```json
{
  "key": "my_viewer",
  "type": "MultiSensorViewer",
  "params": {
    "title": "My Sensors",
    "sensor_keys": ["sensor_a", "sensor_b"],
    "colors": [[255, 0, 0], [0, 255, 0]],
    "labels": ["A", "B"]
  }
}
```

2. `config.ini`의 `[DISPLAY]` 섹션에 활성화 키 추가

```ini
[DISPLAY]
my_viewer=on
```

> **주의:** `"key"` 값이 `config.ini`의 키와 반드시 일치해야 합니다. 불일치 시 항상 활성화됩니다(fallback=True).

**방법 B — Python 프로파일 수정 (dg5w 계열)**

`profiles/<product>.py`의 `create_viewers()`에 튜플 추가:

```python
def create_viewers(config=None):
    return [
        # ... 기존 뷰어 ...
        ("my_viewer", MultiSensorViewer(
            "My Sensors",
            sensor_keys=["sensor_a", "sensor_b"],
            colors=[(255, 0, 0), (0, 255, 0)],
            labels=["A", "B"],
        )),
    ]
```

그 후 동일하게 `config.ini`에 키 추가.

---

### 4.3 뷰어 삭제

**JSON 프로파일:**

1. `profiles/<product>.json`의 `"viewers"` 배열에서 해당 객체 제거
2. `config.ini`의 해당 키 줄 제거

**Python 프로파일:**

1. `create_viewers()` 리스트에서 해당 튜플 제거
2. `config.ini`에서 해당 키 제거

> 삭제한 뷰어만 사용하던 센서가 있다면 함께 정리하세요.

---

### 4.4 뷰어 수정

**JSON 프로파일:** `profiles/<product>.json`에서 해당 viewer 항목의 `"params"` 수정.

```json
{
  "key": "coolant",
  "type": "MultiSensorViewer",
  "params": {
    "title": "Coolant Overview (수정)",
    "sensor_keys": ["coolant_inlet1", "coolant_outlet1"],
    "colors": [[0, 200, 255], [255, 140, 0]],
    "labels": ["IN1", "OUT1"]
  }
}
```

**Python 프로파일:** `create_viewers()`에서 해당 뷰어 인스턴스 수정.

**실행 중 on/off 전환:** `config.ini`는 **5초마다 자동 리로드**됩니다. 파일에서 키를 `on`↔`off` 변경하면 재시작 없이 즉시 반영됩니다.

```ini
coolant=off   # 이 뷰어를 순환에서 제외
coolant=on    # 다시 포함
```

---

### 4.5 새 뷰어 클래스 만들기

`BaseViewer`를 상속하고 `draw()` 메서드를 구현합니다.

```python
# my_viewer.py
from base_viewer import BaseViewer
from config import GRAPH_SIZE
from draw_utils import draw_aligned_text, draw_multi_graph


class MyViewer(BaseViewer):
    def __init__(self, title, sensor_keys, colors, labels):
        super().__init__()
        self.title = title
        self.sensor_keys = sensor_keys
        self.colors = colors
        self.labels = labels

    def draw(self, draw, disp_manager, frame):
        # 1. 화면 초기화 + offset 반환
        offset = self._setup(draw, disp_manager)

        # 2. 표준 2-box 레이아웃 좌표
        graphbox, databox = self._boxes(offset, disp_manager.horizontal)
        gx1, gy1, gx2, gy2 = graphbox
        dx1, dy1, dx2, dy2 = databox

        # 3. 센서 데이터
        sensors = [disp_manager.sensors[k] for k in self.sensor_keys]
        has_data = any(len(s.buffer) >= 2 for s in sensors)
        if not has_data:
            return

        # 4. 그래프 정규화 + 렌더링
        footer_h = 12
        min_val, max_val, norm_list = self._normalize(sensors, GRAPH_SIZE - footer_h)
        self._draw_graph_labels(draw, min_val, max_val,
                                sensors[0].unit_str, gx1, gy1, gy2, GRAPH_SIZE)
        draw_multi_graph(draw, sensors, norm_list, self.colors, graphbox)

        # 5. 타이틀 + 데이터 패널
        dw = dx2 - dx1
        self._draw_title(draw, self.title, dx1, dy1, dw, h=25)
        # ... 값 표시 로직 ...

        # 6. 푸터 (IP 주소, 버전)
        self._draw_footer(draw, disp_manager, dx1, dy2 - footer_h, dw, h=footer_h)
```

**`draw()` 규약:**
- 파라미터: `(self, draw, disp_manager, frame)` — 변경 불가
  - `draw`: PIL `ImageDraw` 객체
  - `disp_manager`: `DisplayManager` 인스턴스 (`.sensors`, `.horizontal`, `.ip_addr` 등)
  - `frame`: 현재 프레임 번호 0~FPS-1 (애니메이션에 사용)
- 데이터가 없으면 조기 `return` (검은 화면 유지)

**JSON 프로파일에서 사용하려면** `profile_loader.py`의 `VIEWER_CLASSES`에 등록:

```python
from my_viewer import MyViewer

VIEWER_CLASSES = {
    ...
    "MyViewer": MyViewer,
}
```

그 후 JSON에서 `"type": "MyViewer"`로 참조.

---

## 5. 프로파일(Profile) 가이드

프로파일은 특정 제품(하드웨어 구성)에 맞는 센서와 뷰어를 정의합니다.
`config.ini`의 `name=<product>` 값으로 로드할 프로파일이 결정됩니다.

### 5.1 프로파일 구조

프로파일 모듈(`profiles/<product>.py`)은 4개 함수를 반드시 구현해야 합니다:

```python
def create_sensors(redis, config=None) -> dict[str, SensorData]:
    """전체 센서 딕셔너리 반환."""

def create_viewers(config=None) -> list[tuple[str, Viewer]]:
    """(config_key, viewer_instance) 튜플 리스트 반환."""

def create_fallback_sensors(redis) -> dict[str, SensorData]:
    """센서 초기화 실패 시 최소한의 안전 센서셋."""

def create_fallback_viewers() -> list[tuple[str, Viewer]]:
    """센서 초기화 실패 시 표시할 기본 뷰어."""
```

두 가지 구현 방식이 있습니다:

| 방식 | 예시 | 특징 |
|------|------|------|
| **Python 방식** | `dg5w.py` | 코드로 직접 정의. 커스텀 로직 자유롭게 작성 가능 |
| **JSON 방식** | `dg5r.py` + `dg5r.json` | JSON 파일에서 선언적으로 정의. `profile_loader.py` 사용 |

---

### 5.2 JSON 프로파일 구조 (`dg5r.json` 형식)

```json
{
  "color_palettes": {
    "MY_COLORS": [[255,60,60], [255,160,0], [0,220,100]]
  },
  "sensors": [ ... ],
  "sensor_templates": [ ... ],
  "viewers": [ ... ]
}
```

#### sensors 항목

```json
{
  "key": "coolant_inlet1",      // SensorData 딕셔너리 키
  "title": "Coolant Inlet(1)",  // 표시 이름
  "unit": "°C",                 // 단위
  "min": 0,                     // 그라데이션 하한
  "max": 100,                   // 그라데이션 상한
  "read_rate": 1,               // 읽기 주기 (초)
  "redis_key": "coolant_temp_inlet1",  // Redis 키 (택1)
  // "redis_keys": ["key1","key2"],    // 복수 키 최대값 (택1)
  // "formula": "float(r.get('a'))/float(r.get('b'))*100",  // 수식 (택1)
  "host_data": "0",             // "1"이면 host 연결 시에만 수집
  "icon": "0xf0510",            // Nerd Font 코드포인트 (선택)
  "label": "IN1"                // 짧은 라벨 (선택)
}
```

#### sensor_templates 항목 (반복 생성)

`{i}` 플레이스홀더와 `count` 키를 사용하면 `config.ini`의 값만큼 자동 반복 생성합니다.

```json
{
  "key": "gpu_temp_{i}",
  "count": "gpu_count",         // config.ini [PRODUCT] gpu_count 값만큼 반복
  "title": "GPU{i} Temp",
  "unit": "°C",
  "min": 10, "max": 120,
  "read_rate": 1,
  "redis_key": "gpu_temp_{i}",
  "host_data": "1",
  "icon": "0xf0510",
  "label": "G{i}"
}
```

#### viewers 항목

```json
{
  "key": "coolant",             // config.ini의 [DISPLAY] 키와 일치해야 함
  "type": "MultiSensorViewer",  // VIEWER_CLASSES에 등록된 클래스명
  "params": {
    "title": "Coolant Overview",
    "sensor_keys": ["coolant_inlet1", "coolant_outlet1"],
    "colors": [[0,200,255], [255,140,0]],
    "labels": ["IN1", "OUT1"]
  }
}
```

**`expand` 키** — sensor_templates처럼 동적 확장:

```json
{
  "key": "gpu",
  "type": "TempUtilViewer",
  "expand": "gpu_count",        // config.ini [PRODUCT] gpu_count 참조
  "params": {
    "temp_title": "GPU Temperature",
    "util_title": "GPU Power",
    "sensor_keys": "gpu_temp_{i}",   // {i}가 자동 확장되어 리스트가 됨
    "colors": "$GPU_COLORS",         // $ 접두사로 color_palettes 참조
    "labels": "G{i}",
    "util_keys": "gpu_power_{i}"
  }
}
```

---

### 5.3 프로파일 추가

**JSON 방식 (권장):**

1. `profiles/my_product.json` 생성 (센서, 뷰어 정의)
2. `profiles/my_product.py` 생성

```python
# profiles/my_product.py
import os
from profile_loader import load_sensors, load_viewers

_JSON = os.path.join(os.path.dirname(__file__), 'my_product.json')

def create_sensors(redis, config=None):
    return load_sensors(_JSON, redis, config)

def create_viewers(config=None):
    return load_viewers(_JSON, config)

def create_fallback_sensors(redis):
    from sensor_data import SensorData
    return {
        "my_sensor": SensorData("My Sensor", "°C", 0, 100,
                                read_rate=1, redis=redis,
                                redis_key='my_redis_key'),
    }

def create_fallback_viewers():
    from viewer import SensorViewer
    return [("my_viewer", SensorViewer("My Sensor", sensor_key="my_sensor"))]
```

3. `config.ini` 업데이트

```ini
[PRODUCT]
name=my_product
```

**Python 방식:**

`profiles/my_product.py`에 `create_sensors()`와 `create_viewers()`를 직접 Python 코드로 작성합니다. `dg5w.py`를 참고하세요.

---

### 5.4 프로파일 수정

#### 센서 추가

**JSON:** `"sensors"` 배열에 항목 추가

```json
{
  "key": "new_sensor",
  "title": "New Sensor",
  "unit": "°C",
  "min": 0, "max": 100,
  "read_rate": 1,
  "redis_key": "new_redis_key"
}
```

**Python:** `create_sensors()` 딕셔너리에 항목 추가

```python
"new_sensor": SensorData(
    "New Sensor", "°C", 0, 100,
    read_rate=1, redis=r,
    redis_key='new_redis_key',
),
```

#### 센서 삭제

1. `sensors`(또는 `sensor_templates`) 배열에서 해당 항목 제거
2. 해당 센서 키를 참조하는 **모든 뷰어**(`sensor_key`, `sensor_keys`, `sub1_key`, `delta_key` 등)에서 제거
3. `create_fallback_sensors()`에 있다면 함께 제거

#### 센서 수정

`"title"`, `"unit"`, `"min"`, `"max"`, `"redis_key"`, `"icon"`, `"label"` 등 원하는 필드를 직접 편집합니다.

---

### 5.5 프로파일 삭제

1. `profiles/<product>.py` 삭제
2. `profiles/<product>.json` 삭제 (있는 경우)
3. 다른 `config.ini`에서 `name=<product>`를 참조하지 않는지 확인

---

## 6. config.ini 레퍼런스

```ini
[PRODUCT]
name=dg5r              # 로드할 프로파일 (profiles/ 디렉토리 내 모듈명)
version=gadgetini v0.36
redis_host=localhost
redis_port=6379
gpu_count=8            # sensor_templates / expand에서 {i} 반복 수
cpu_count=2

[DISPLAY]
orientation=horizontal  # horizontal | vertical
display=on              # off → 화면 꺼짐 (검은 화면)
rotation_sec=3          # 뷰어 자동 전환 간격 (초)
leak=on                 # 누수 감지 활성화 (5초 연속 감지 시 경고 화면)

# 뷰어 활성화 키 (create_viewers()에서 반환한 첫 번째 값과 일치)
coolant=on
coolant_detail=on
chassis=on
gpu=on
cpu=on
memory=on
coolant_daily=on
gpu_daily=on
cpu_daily=on
```

> `config.ini`는 **5초마다 자동 리로드**됩니다. 재시작 없이 수정 사항이 즉시 반영됩니다.

---

## 7. 개발 모드

### 가상 LCD 모드 (하드웨어 없이 개발)

`config.py` 상단의 플래그를 변경하세요:

```python
DEBUG = 1            # 모든 박스에 디버그 테두리 표시
USE_VIRTUAL_LCD = True   # 실제 LCD 대신 OpenCV 창 사용
USE_REAL_DATA = False    # Redis 없이 랜덤 데이터로 동작
```

### 실행

```bash
cd ~/gadgetini/src/display
python3 display_main.py
```

### 자주 쓰는 Nerd Font 아이콘

| 아이콘 | 유니코드 (JSON) | Python | 용도 |
|--------|---------------|--------|------|
| 󰔐 | `"0xf0510"` | `"\U000f0510"` | 온도 |
| 󰖎 | `"0xf058e"` | `"\U000f058e"` | 습도 |
| 󰐥 | `"0xf0ee0"` | `"\U000f0ee0"` | CPU |
| 󰍛 | `"0xf035b"` | `"\U000f035b"` | 메모리 |
| 󰐋 | `"0xf140b"` | `"\U000f140b"` | 전력 |
