# Gadgetini Web UI — Font Style Guide

글씨 크기, 무게, 간격을 통합하여 일관된 계층 구조와 가독성을 제공합니다.

---

## 폰트 크기 규칙

모든 텍스트는 다음 규칙을 따릅니다:

### Level 1: 페이지/섹션 제목 (Page/Major Headings)
- **용도**: 페이지 제목, 매우 중요한 섹션 헤더
- **크기**: `text-lg sm:text-xl`
- **무게**: `font-bold`
- **자간**: `tracking-wider`
- **색상**: `text-gray-800` 또는 `text-white` (배경에 따라)
- **예시**: 페이지 타이틀, 주요 섹션 헤더

**❌ 예시 (잘못됨):**
```jsx
<p className="text-base font-bold">{title}</p>  // 너무 작음
```

**✅ 예시 (올바름):**
```jsx
<h1 className="text-lg sm:text-xl font-bold tracking-wider">{title}</h1>
```

---

### Level 2: 섹션/카드 헤더 (Section Headers)
- **용도**: SectionHeader 컴포넌트, 카드 제목, 부분 제목
- **크기**: `text-base sm:text-base` (반응형 기본값)
- **무게**: `font-bold`
- **자간**: `tracking-wider`
- **색상**: `text-gray-700` 또는 `text-white/90`
- **예시**: "General", "PWM Duty", "Fan Curve (Auto)"

**✅ 구현 예시:**
```jsx
<h2 className="text-base font-bold text-gray-700 uppercase tracking-wider">
  {label}
</h2>
```

---

### Level 3: 필드 라벨/입력 레이블 (Form Labels)
- **용도**: 폼 필드 라벨, 인풋 위의 설명 텍스트
- **크기**: `text-xs sm:text-sm`
- **무게**: `font-bold` 또는 `font-semibold`
- **자간**: `tracking-wider` 또는 기본값
- **색상**: `text-gray-500` 또는 `text-gray-600`
- **예시**: "Idle Temp (°C)", "Current IP", "Max PWM (%)"

**✅ 구현 예시:**
```jsx
<label className="flex flex-col gap-0.5 sm:gap-1">
  <span className="text-xs sm:text-sm text-gray-600 font-bold uppercase">
    Idle Temp (°C)
  </span>
  <input type="number" ... />
</label>
```

---

### Level 4: 바디/값 텍스트 (Body Text / Values)
- **용도**: 주요 본문, 읽을 텍스트, 데이터 값
- **크기**: `text-base` (일반 내용), `text-sm` (압축된 공간)
- **무게**: `font-semibold` 또는 기본값
- **색상**: `text-gray-800` (주요), `text-gray-700` (부)
- **자간**: 기본값 (tracking-wider 없음)
- **예시**: IP 주소, 온도값, 상태 메시지

**✅ 구현 예시:**
```jsx
<p className="text-base font-semibold text-gray-800">
  {currentIP}
</p>
```

---

### Level 5: 보조/설명 텍스트 (Secondary / Helper Text)
- **용도**: 작은 설명, 부가 정보, 툴팁
- **크기**: `text-xs sm:text-sm`
- **무게**: 기본값 또는 `font-semibold`
- **색상**: `text-gray-500` 또는 `text-gray-400`
- **자간**: 기본값
- **예시**: "eth0 not detected", "기본 온도 이하: 기본 PWM"

**✅ 구현 예시:**
```jsx
<p className="text-xs sm:text-sm text-gray-500">
  {t("display_master")}
</p>
```

---

### Level 6: 메타/보조 정보 (Meta Information)
- **용도**: 아주 작은 정보, 상태 배지, 아이콘 라벨
- **크기**: `text-[10px] sm:text-xs` (매우 작음 필요 시) 또는 `text-xs`
- **무게**: `font-bold` (배지/강조), 기본값 (일반)
- **색상**: `text-gray-400` 또는 `text-gray-500`
- **자간**: `tracking-wider` (배지), 기본값 (일반)
- **예시**: "Settings", "Live", "SELECTED" 배지, "CH1", "Hz" 단위

**✅ 구현 예시:**
```jsx
<span className="text-[10px] sm:text-xs text-gray-400 font-bold uppercase tracking-wider">
  {t("settings_label")}
</span>
```

---

## 반응형 폰트 크기 가이드

모든 텍스트는 **모바일 우선** 원칙을 따릅니다:

| 레벨 | 모바일 | 데스크톱 (sm 이상) |
|------|--------|-----------------|
| L1 (Page Title) | `text-lg` | `text-xl` |
| L2 (Section) | `text-base` | `text-base` |
| L3 (Label) | `text-xs` | `text-sm` |
| L4 (Body) | `text-sm` | `text-base` |
| L5 (Helper) | `text-xs` | `text-sm` |
| L6 (Meta) | `text-[10px]` | `text-xs` |

**패턴:**
```jsx
className="text-xs sm:text-sm"     // 기본 패턴: 작음 → 보통
className="text-sm sm:text-base"   // 일반 텍스트: 보통 → 크게
className="text-base sm:text-base" // 단일 크기 (보통은 변경 불필요)
```

---

## 폰트 무게 (Font Weight) 규칙

| 무게 | Tailwind | 용도 | 예시 |
|------|----------|------|------|
| Light | `font-light` | 거의 사용 안 함 | - |
| Normal | (기본값) | 보조 설명, 본문 | 설명 텍스트 |
| Semibold | `font-semibold` | 강조 필요한 본문, 입력값 | "37.2°C", "Active" |
| Bold | `font-bold` | 제목, 라벨, 배지 | "Current IP", "SELECTED" |

**규칙:**
- **제목/라벨**: 항상 `font-bold`
- **본문/값**: `font-semibold` 또는 기본값 (중요도에 따라)
- **보조**: 기본값 (`font-normal`)

---

## 자간 (Letter Spacing) 규칙

| 값 | Tailwind | 용도 |
|----|----------|------|
| Tighter | `tracking-tighter` | 거의 사용 안 함 |
| Normal | (기본값) | 본문, 값 |
| Wider | `tracking-wider` | 라벨, 배지, 섹션 헤더 |
| Widest | `tracking-widest` | 매우 강조된 헤더 (거의 없음) |

**규칙:**
- **UPPERCASE 텍스트**: 항상 `tracking-wider` 이상
- **일반 텍스트**: 기본값 (tracking 미지정)
- **강조 필요**: `tracking-wider` 고려

---

## 색상 규칙 (Color Hierarchy)

### 텍스트 색상 계층

| 용도 | 색상 | 예시 |
|------|------|------|
| 매우 강조 | `text-gray-900` 또는 `text-white` | 제목, 중요 값 |
| 주요 | `text-gray-800` | 본문, 필드명 |
| 보조 | `text-gray-700` | 부설명 |
| 약한 | `text-gray-500` 또는 `text-gray-600` | 라벨, 도움말 |
| 매우 약한 | `text-gray-400` | 메타 정보, 아이콘 |

**❌ 잘못된 예시:**
```jsx
<span className="text-gray-600">Important Value</span>  // 너무 연함
```

**✅ 올바른 예시:**
```jsx
<span className="text-gray-800 font-semibold">Important Value</span>
```

---

## 체크리스트: 폰트 일관성 점검

새로운 텍스트 추가 시 다음을 확인하세요:

- [ ] 계층 구조에 맞는 크기인가? (Level 1-6 중 하나)
- [ ] 반응형 크기가 정의되어 있는가? (`sm:text-*` 포함)
- [ ] 무게가 적절한가? (제목은 bold, 본문은 semibold 또는 normal)
- [ ] 색상이 계층에 맞는가? (주요는 gray-800, 보조는 gray-500)
- [ ] UPPERCASE는 `tracking-wider` 또는 `tracking-widest`를 포함하는가?
- [ ] 충분한 대비가 있는가? (배경 대비 가독성)

---

## 예제: 통합 폼 필드

```jsx
<div className="flex flex-col gap-0.5 sm:gap-1">
  {/* Level 3: 필드 라벨 */}
  <span className="text-xs sm:text-sm text-gray-600 font-bold uppercase tracking-wider">
    Idle Temp (°C)
  </span>
  
  {/* Level 4: 입력 값 (폼 내부) */}
  <input
    type="number"
    value={value}
    className="text-xs sm:text-base font-semibold"
  />
  
  {/* Level 5: 보조 설명 */}
  <p className="text-xs text-gray-500">
    기본 온도 이하에서 기본 PWM을 사용합니다.
  </p>
</div>
```

---

## 예제: 데이터 표시 (Key-Value)

```jsx
<div className="flex items-center justify-between">
  {/* 라벨 (Level 3) */}
  <span className="text-xs sm:text-sm text-gray-600 font-semibold">
    Current IP:
  </span>
  
  {/* 값 (Level 4) */}
  <span className="text-base font-semibold text-gray-800">
    192.168.1.100
  </span>
</div>
```

---

## 예제: 섹션 헤더

```jsx
<div className="bg-slate-800 px-4 py-2">
  {/* Level 2: 섹션 헤더 */}
  <span className="text-base font-bold uppercase tracking-wider text-white/90">
    PWM Duty
  </span>
</div>
```

---

## 자주하는 실수

| 실수 | 원인 | 해결책 |
|------|------|--------|
| 텍스트가 모바일에서 너무 작음 | `text-xs`만 사용 | `text-xs sm:text-sm` 추가 |
| 라벨이 너무 약해 보임 | 무게 미지정 | `font-bold` 추가 |
| UPPERCASE가 뭉쳐 보임 | tracking 없음 | `tracking-wider` 추가 |
| 제목이 본문과 구분 안 됨 | 무게/크기 동일 | `font-bold text-lg sm:text-xl` |
| 색상 대비 낮음 | 약한 색상 사용 | `text-gray-700` 이상 사용 |

---

## 관련 파일

- **Main Component**: `src/gui/gadgetini-web/app/components/settings.js`
- **i18n**: `src/gui/gadgetini-web/app/i18n.js` (모든 텍스트 문자열)
- **Global CSS**: `src/gui/gadgetini-web/app/globals.css` (필요시)

---

**마지막 업데이트**: 2026-08-25  
**상태**: Active (이 가이드라인을 따르도록 전체 UI 점검 필요)
