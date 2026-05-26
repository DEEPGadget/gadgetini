"use client";
// Minimal i18n — React Context + localStorage. No external dependency.
//
// Usage:
//   <LocaleProvider> { children } </LocaleProvider>   — once at the top of page.js
//   const { locale, setLocale, t } = useLocale();      — inside components
//   t("save")                                          — key → string for the current locale
//
// When adding a new key, write it in both languages. Missing keys fall back to en,
// and if en is also missing, the key itself is returned.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const STRINGS = {
  en: {
    // === Header / Reboot ===
    reboot: "Gadgetini Reboot",
    rebooting: "Rebooting...",
    reboot_confirm: "System will reboot. Proceed?",
    reboot_sent: "Reboot command sent. The system may go down shortly.",
    reboot_failed: "Failed to reboot",

    // === Sidebar ===
    settings: "Settings",

    // === Section headers ===
    section_system: "System",
    section_general: "General",
    section_hardware_count: "Hardware Count",
    section_compute: "Compute",
    section_cooling_chassis: "Cooling & Chassis",
    section_daily_graphs: "Daily Graphs",
    section_pcb_status: "PCB Status",
    section_pwm_duty: "PWM Duty (read-only)",
    section_lcd_control: "LCD Control",
    section_control_board: "Control Board",
    fan_curve_title: "Fan Curve (Auto)",

    // === System block ===
    current_ip: "Current IP",
    eth0_active: "eth0 active",
    eth0_inactive: "eth0 not detected",
    eth0_warning: "⚠ eth0 not connected — IP update unavailable",
    server: "Server",
    open_dashboard: "Open Dashboard",
    network_mode: "Network Mode",
    ip_address: "IP Address",
    prefix_length: "Prefix Length (e.g. 24)",
    gateway: "Gateway",
    dns1: "DNS 1 (optional)",
    dns2: "DNS 2 (optional)",
    update_ip: "Update IP",
    updating: "Updating...",
    ip_change_confirm: "Are you sure you want to change the IP?",
    ip_update_failed: "Failed to update IP",
    config_update_failed: "Failed to update config",

    // === Display / LCD ===
    display: "Display",
    display_master: "LCD master on/off",
    orientation: "Orientation",
    vertical: "Vertical",
    horizontal: "Horizontal",
    rotation: "Rotation",
    rotation_desc: "Panel switch interval",
    sec_unit: "sec",
    gpu_count: "GPU Count",
    cpu_count: "CPU Count",
    fan_count: "Fan Count",
    cpu: "CPU",
    gpu: "GPU",
    memory: "Memory",
    chassis: "Chassis",
    coolant: "Coolant",
    coolant_detail: "Coolant Detail",
    coolant_flow: "Coolant Flow",
    fan_rpm: "Fan RPM",
    leak: "Leak",
    cpu_daily: "CPU Daily",
    gpu_daily: "GPU Daily",
    coolant_daily: "Coolant Daily",
    apply: "Apply",

    // === Control Board status ===
    service_active: "Service Active",
    service_inactive: "Service Inactive",
    pcb_connected: "PCB Connected",
    pcb_timeout: "PCB Timeout",
    pcb_disconnected: "PCB Disconnected",
    pcb_status_unknown: "PCB Status Unknown",
    mode: "Mode",
    auto: "Auto",
    manual: "Manual",
    tbd_short: "(TBD)",
    manual_tbd: "TBD — Manual mode not yet implemented",
    service_inactive_warning: "⚠ control_board.service inactive — controls disabled",
    pcb_unreachable_warning: "⚠ PCB unreachable — controls disabled",

    // === PWM duty section ===
    pumps_label: "Pumps · CH 1~4",
    fans_label: "Fans · CH 5~12",
    estimated_flow: "Est. flow",

    // === Fan curve ===
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
    service_inactive_tooltip: "control_board.service is inactive",
  },
  ko: {
    // === Header / Reboot ===
    reboot: "Gadgetini 재부팅",
    rebooting: "재부팅 중...",
    reboot_confirm: "시스템이 재부팅됩니다. 계속할까요?",
    reboot_sent: "재부팅 명령이 전송되었습니다. 곧 시스템이 종료됩니다.",
    reboot_failed: "재부팅 실패",

    // === Sidebar ===
    settings: "설정",

    // === Section headers ===
    section_system: "시스템",
    section_general: "일반",
    section_hardware_count: "하드웨어 수량",
    section_compute: "컴퓨트",
    section_cooling_chassis: "냉각 · 섀시",
    section_daily_graphs: "일별 그래프",
    section_pcb_status: "PCB 상태",
    section_pwm_duty: "PWM Duty (읽기 전용)",
    section_lcd_control: "LCD 제어",
    section_control_board: "제어 보드",
    fan_curve_title: "팬 곡선 (자동)",

    // === System block ===
    current_ip: "현재 IP",
    eth0_active: "eth0 활성",
    eth0_inactive: "eth0 미감지",
    eth0_warning: "⚠ eth0 미연결 — IP 변경 불가",
    server: "서버",
    open_dashboard: "대시보드 열기",
    network_mode: "네트워크 모드",
    ip_address: "IP 주소",
    prefix_length: "Prefix 길이 (예: 24)",
    gateway: "게이트웨이",
    dns1: "DNS 1 (선택)",
    dns2: "DNS 2 (선택)",
    update_ip: "IP 변경",
    updating: "변경 중...",
    ip_change_confirm: "정말 IP 를 변경하시겠습니까?",
    ip_update_failed: "IP 변경 실패",
    config_update_failed: "설정 변경 실패",

    // === Display / LCD ===
    display: "디스플레이",
    display_master: "LCD 마스터 on/off",
    orientation: "방향",
    vertical: "세로",
    horizontal: "가로",
    rotation: "전환",
    rotation_desc: "패널 전환 간격",
    sec_unit: "초",
    gpu_count: "GPU 개수",
    cpu_count: "CPU 개수",
    fan_count: "팬 개수",
    cpu: "CPU",
    gpu: "GPU",
    memory: "메모리",
    chassis: "섀시",
    coolant: "냉각수",
    coolant_detail: "냉각수 상세",
    coolant_flow: "냉각수 유량",
    fan_rpm: "팬 RPM",
    leak: "누수",
    cpu_daily: "CPU 일별",
    gpu_daily: "GPU 일별",
    coolant_daily: "냉각수 일별",
    apply: "적용",

    // === Control Board status ===
    service_active: "서비스 활성",
    service_inactive: "서비스 비활성",
    pcb_connected: "PCB 연결됨",
    pcb_timeout: "PCB 타임아웃",
    pcb_disconnected: "PCB 분리됨",
    pcb_status_unknown: "PCB 상태 불명",
    mode: "모드",
    auto: "자동",
    manual: "수동",
    tbd_short: "(예정)",
    manual_tbd: "예정 — 수동 모드 미구현",
    service_inactive_warning: "⚠ control_board.service 비활성 — 제어 불가",
    pcb_unreachable_warning: "⚠ PCB 응답 없음 — 제어 불가",

    // === PWM duty section ===
    pumps_label: "펌프 · CH 1~4",
    fans_label: "팬 · CH 5~12",
    estimated_flow: "추정 유량",

    // === Fan curve ===
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
    service_inactive_tooltip: "control_board.service 가 비활성 상태",
  },
};

const LocaleContext = createContext({
  locale: "en",
  setLocale: () => {},
  t: (k) => k,
});

export function LocaleProvider({ children }) {
  const [locale, setLocaleState] = useState("en");

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
