"use client";
// Minimal i18n — React Context + localStorage. No external dependency.
//
// 사용:
//   <LocaleProvider> { children } </LocaleProvider>   — page.js 최상위에서 한 번
//   const { locale, setLocale, t } = useLocale();      — 컴포넌트 안에서
//   t("save")                                          — 키 → 현재 locale 의 문자열
//
// 새 키 추가 시 두 언어 모두에 작성. 누락된 키는 en fallback, en 도 없으면 키 자체 반환.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const STRINGS = {
  en: {
    reboot: "Gadgetini Reboot",
    rebooting: "Rebooting...",
    reboot_confirm: "System will reboot. Proceed?",
    reboot_sent: "Reboot command sent. The system may go down shortly.",
    reboot_failed: "Failed to reboot",
    fan_curve_title: "Fan Curve (Auto)",
    fan_curve_desc:
      "Below idle temp: idle PWM. Above warning temp: max PWM. Linear interpolation between.",
    idle_group: "Idle",
    warning_group: "Warning",
    idle_temp: "Idle Temp (°C)",
    warning_temp: "Warning Temp (°C)",
    idle_pwm: "Idle PWM (%)",
    max_pwm: "Max PWM (%)",
    save: "Save",
    save_failed: "Failed to save fan curve",
    loading: "Loading...",
    service_inactive: "control_board.service is inactive",
  },
  ko: {
    reboot: "Gadgetini 재부팅",
    rebooting: "재부팅 중...",
    reboot_confirm: "시스템이 재부팅됩니다. 계속할까요?",
    reboot_sent: "재부팅 명령이 전송되었습니다. 곧 시스템이 종료됩니다.",
    reboot_failed: "재부팅 실패",
    fan_curve_title: "팬 곡선 (자동)",
    fan_curve_desc:
      "기본 온도 이하: 기본 PWM 으로 idle. 경고 온도 이상: 최대 PWM 도달. 그 사이는 선형 보간.",
    idle_group: "기본",
    warning_group: "경고",
    idle_temp: "기본 온도 (°C)",
    warning_temp: "경고 온도 (°C)",
    idle_pwm: "기본 PWM (%)",
    max_pwm: "최대 PWM (%)",
    save: "저장",
    save_failed: "팬 곡선 저장 실패",
    loading: "불러오는 중...",
    service_inactive: "control_board.service 가 비활성 상태",
  },
};

const LocaleContext = createContext({
  locale: "en",
  setLocale: () => {},
  t: (k) => k,
});

export function LocaleProvider({ children }) {
  const [locale, setLocaleState] = useState("en");

  // localStorage 초기 로드 — SSR 시 window 없으므로 useEffect 안에서
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem("locale");
    if (saved === "en" || saved === "ko") setLocaleState(saved);
  }, []);

  const setLocale = useCallback((l) => {
    if (l !== "en" && l !== "ko") return;
    setLocaleState(l);
    if (typeof window !== "undefined") window.localStorage.setItem("locale", l);
  }, []);

  const t = useCallback(
    (key) => STRINGS[locale]?.[key] ?? STRINGS.en[key] ?? key,
    [locale]
  );

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}
