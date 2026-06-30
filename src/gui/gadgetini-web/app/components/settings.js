"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  ArrowUpIcon,
  ArrowRightIcon,
  CheckIcon,
  ArrowTopRightOnSquareIcon,
} from "@heroicons/react/24/solid";
import LoadingSpinner from "../utils/LoadingSpinner";
import { getDisplayConfig } from "../utils/display/getDisplayConfig";
import { useLocale } from "../i18n";

function Toggle({ value, onChange }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onChange();
      }}
      className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
        value ? "bg-green-400" : "bg-gray-300"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-transform duration-200 ${
          value ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function SectionHeader({ label, colorClass }) {
  return (
    <div className={`px-4 py-2.5 ${colorClass}`}>
      <span className="text-xs font-bold uppercase tracking-widest text-white/90">
        {label}
      </span>
    </div>
  );
}

function GridCard({ label, stateKey, displayMode, setDisplayMode, activeClass }) {
  const isOn = displayMode[stateKey];
  return (
    <button
      onClick={() =>
        setDisplayMode((p) => ({ ...p, [stateKey]: !p[stateKey] }))
      }
      className={`rounded-xl p-3 flex flex-col gap-2 text-left w-full transition-all duration-200 ${
        isOn ? activeClass : "bg-gray-100 border border-gray-200 text-gray-400"
      }`}
    >
      <span className="text-sm font-semibold leading-tight">{label}</span>
      <span className="text-xs font-bold opacity-75">
        {isOn ? "● ON" : "○ OFF"}
      </span>
    </button>
  );
}

const SERVERS = [
  { label: "dg5R", value: "dg5r" },
  { label: "dg5W", value: "dg5w" },
];

export default function Settings() {
  const { t } = useLocale();
  const [currentIP, setCurrentIP] = useState("localhost");
  const [ethActive, setEthActive] = useState(false);
  const [serverName, setServerName] = useState("dg5r");
  const [displayMode, setDisplayMode] = useState({
    orientation: "vertical",
    display: true,
    coolant: false,
    coolant_detail: true,
    coolant_flow: true,
    chassis: true,
    cpu: true,
    gpu: true,
    memory: true,
    fan_rpm: true,
    coolant_daily: true,
    gpu_daily: true,
    cpu_daily: true,
    nvme: true,
    psu: false,
    leak: true,
    rotationTime: 7,
    gpuCount: 8,
    cpuCount: 2,
    nvmeCount: 2,
  });
  const [IPMode, setIPMode] = useState("dhcp");
  const IPRefs = useRef({
    ip: "",
    netmask: "",
    gateway: "",
    dns1: "",
    dns2: "",
    mode: IPMode,
  });
  useEffect(() => {
    IPRefs.current.mode = IPMode;
  }, [IPMode]);

  const [loadingState, setLoadingState] = useState({
    updateIP: false,
    applyDisplayConfig: false,
  });

  // === Control Board state ===
  // status: { pcb_connected, comm_status, mode }
  // active = pcb_connected (single gate for UI enabled/disabled)
  const [cbStatus, setCbStatus] = useState({
    active: false,
    pcb_connected: false,
    comm_status: "unknown",
    mode: "auto",
  });
  // Pending (unsaved) mode selection — applied only when the user clicks Save.
  const [pendingMode, setPendingMode] = useState("auto");
  const [modeSaving, setModeSaving] = useState(false);
  const [cbPwm, setCbPwm] = useState({
    pump: [null, null, null, null],
    fan: [null, null, null, null, null, null, null, null],
    fanRpm: [null, null, null, null, null, null, null, null],
    coolantFlowLpm: null,
    curvePump: [], // pump channels the controller/manual drives (rest are fixed)
    curveFan: [], // fan channels the curve/manual drives (rest are fixed, e.g. CH10)
  });
  const [fanCurve, setFanCurve] = useState({
    min_temp: 25,
    max_temp: 60,
    min_duty: 100,
    max_duty: 1000,
  });
  const [fanCurveLoading, setFanCurveLoading] = useState(true);
  const [fanCurveSaving, setFanCurveSaving] = useState(false);
  const [manualPwm, setManualPwm] = useState({
    pump: [500, 500, 500, 500],
    fan: [500, 500, 500, 500, 500, 500, 500, 500],
  });
  const [manualPwmSaving, setManualPwmSaving] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState(new Set());
  const [inputValue, setInputValue] = useState("");

  // Always sync manualPwm with current Redis values (cbPwm)
  // This ensures UI displays actual hardware state, not stale placeholders
  useEffect(() => {
    if (cbPwm.pump.some(v => v !== null) || cbPwm.fan.some(v => v !== null)) {
      setManualPwm({
        pump: cbPwm.pump.map(v => (v !== null ? Math.round(v / 10) : 500)),
        fan: cbPwm.fan.map(v => (v !== null ? Math.round(v / 10) : 500))
      });
    }
  }, [cbPwm.pump, cbPwm.fan]);

  useEffect(() => {
    getDisplayConfig().then(setDisplayMode);

    fetch("/api/hardware-count")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setDisplayMode((p) => ({
          ...p,
          ...(d.gpuCount > 0 ? { gpuCount: d.gpuCount } : {}),
          ...(d.cpuCount > 0 ? { cpuCount: d.cpuCount } : {}),
          ...(d.nvmeCount >= 0 ? { nvmeCount: d.nvmeCount } : {}),
        }));
      })
      .catch(() => {});

    fetch("/api/ip/self")
      .then((r) => r.json())
      .then((d) => {
        setCurrentIP(d?.ip ?? "localhost");
        setEthActive(d?.ethActive ?? false);
      });
    fetch("/api/server-select")
      .then((r) => r.json())
      .then((d) => { if (d.server) setServerName(d.server); });
  }, []);

  const handleServerChange = async (value) => {
    setServerName(value);
    await fetch("/api/server-select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ server: value }),
    });
  };

  const handleIPChange = async () => {
    if (!window.confirm(t("ip_change_confirm"))) {
      return;
    }
    setLoadingState({ ...loadingState, updateIP: true });
    const payload = {
      ip: IPRefs.current.ip?.value || "",
      netmask: IPRefs.current.netmask?.value || "",
      gateway: IPRefs.current.gateway?.value || "",
      dns1: IPRefs.current.dns1?.value || "",
      dns2: IPRefs.current.dns2?.value || "",
      mode: IPMode,
    };
    try {
      const response = await fetch("/api/ip/self", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        const data = await response.json();
        alert(
          `IP updated\nmethod:${data.mode}\naddress:${data.ip}/${data.netmask}\ngateway: ${data.gateway}\ndns1: ${data.dns1}\ndns2: ${data.dns2} `
        );
      } else {
        const message = await response.json();
        alert(`${t("ip_update_failed")} \n ${message.error}`);
      }
    } catch (error) {
      console.log(error);
    } finally {
      setLoadingState({ ...loadingState, updateIP: false });
    }
  };

  const handleDisplayMode = async () => {
    setLoadingState({ ...loadingState, applyDisplayConfig: true });
    try {
      const response = await fetch("/api/display-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(displayMode),
      });
      if (response.ok) {
        console.log("Config updated successfully");
      } else {
        const message = await response.json();
        alert(`${t("config_update_failed")} \n ${message.error}`);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoadingState({ ...loadingState, applyDisplayConfig: false });
    }
  };

  // === Control Board polls ===
  // Status: 5s cadence — check whether PCB is connected (comm_status === 'ok')
  useEffect(() => {
    const fetchStatus = () =>
      fetch("/api/control/status")
        .then((r) => r.json())
        .then(setCbStatus)
        .catch(() => {});
    fetchStatus();
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, []);

  // Keep the pending selection in sync with the actual mode — only fires when the actual
  // mode value changes (e.g. after a save), so an in-progress selection isn't clobbered.
  useEffect(() => {
    setPendingMode(cbStatus.mode);
  }, [cbStatus.mode]);

  // PWM duty readback: 500ms cadence — pump CH1~4 + fan CH5~12 (fixed 8 slots).
  // The API reads the wiring.pwm mapping and remaps to physical channel positions.
  // Fan RPM and estimated pump flow are refreshed on the same cadence.
  // 500ms interval ensures faster feedback when manual PWM is applied by data_crawler.
  useEffect(() => {
    const fetchPwm = () =>
      fetch("/api/control/pwm")
        .then((r) => r.json())
        .then((d) => {
          if (d && Array.isArray(d.pump) && Array.isArray(d.fan)) {
            setCbPwm({
              pump: d.pump,
              fan: d.fan,
              fanRpm: Array.isArray(d.fanRpm) ? d.fanRpm : Array(d.fan.length).fill(null),
              coolantFlowLpm:
                typeof d.coolantFlowLpm === "number" ? d.coolantFlowLpm : null,
              curvePump: Array.isArray(d.wiredPumpChannels) ? d.wiredPumpChannels : [],
              curveFan: Array.isArray(d.wiredFanChannels) ? d.wiredFanChannels : [],
            });
          }
        })
        .catch(() => {});
    fetchPwm();
    const id = setInterval(fetchPwm, 500);
    return () => clearInterval(id);
  }, []);

  // fan_curve: fetch only once initially (so external changes don't overwrite edits in progress)
  useEffect(() => {
    setFanCurveLoading(true);
    fetch("/api/control/fan-curve")
      .then((r) => r.json())
      .then((d) => {
        if (
          d &&
          typeof d.min_temp === "number" &&
          typeof d.max_temp === "number" &&
          typeof d.min_duty === "number" &&
          typeof d.max_duty === "number"
        ) {
          setFanCurve(d);
        }
      })
      .catch(() => {})
      .finally(() => setFanCurveLoading(false));
  }, []);


  const handleFanCurveSave = async () => {
    setFanCurveSaving(true);
    try {
      const r = await fetch("/api/control/fan-curve", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fanCurve),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(`${t("save_failed")}: ${e.error || r.status}`);
      }
    } catch (err) {
      alert(`${t("save_failed")}: ${err?.message || err}`);
    } finally {
      setFanCurveSaving(false);
    }
  };

  const handleModeChange = async (newMode) => {
    setModeSaving(true);
    try {
      // Always use /api/control/mode for mode changes to ensure Redis is updated
      const r = await fetch("/api/control/mode", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: newMode }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(`${t("save_failed")}: ${e.error || r.status}`);
        return;
      }

      // When switching to manual, also seed current PWM values
      if (newMode === "manual") {
        const curPump = Array.isArray(cbPwm?.pump) ? cbPwm.pump : [];
        const curFan = Array.isArray(cbPwm?.fan) ? cbPwm.fan : [];
        const pumpDuty = Array.from({ length: 4 }, (_, i) =>
          curPump[i] != null ? curPump[i] : 500
        );
        const fanDuty = Array.from({ length: 8 }, (_, i) =>
          curFan[i] != null ? curFan[i] : 500
        );
        setManualPwm({
          pump: pumpDuty.map((v) => Math.round(v / 10)),
          fan: fanDuty.map((v) => Math.round(v / 10)),
        });
        // Save PWM values in config
        const pwmR = await fetch("/api/control/pwm", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pump: pumpDuty, fan: fanDuty }),
        });
        if (!pwmR.ok) {
          console.warn("PWM seed failed (non-critical)");
        }
      }

      setCbStatus((p) => ({ ...p, mode: newMode }));
    } catch (err) {
      alert(`${t("save_failed")}: ${err?.message || err}`);
    } finally {
      setModeSaving(false);
    }
  };

  const handleManualPwmSave = async () => {
    if (selectedChannels.size === 0) {
      alert("Please select at least one channel");
      return;
    }

    setManualPwmSaving(true);
    try {
      // Copy current PWM values, only update selected channels
      const pumpPayload = [...cbPwm.pump];
      const fanPayload = [...cbPwm.fan];

      selectedChannels.forEach((chId) => {
        if (chId.startsWith("pump-")) {
          const idx = parseInt(chId.split("-")[1], 10);
          if (idx >= 0 && idx < 4) {
            pumpPayload[idx] = Math.min(1000, Math.max(0, manualPwm.pump[idx] * 10));
          }
        } else if (chId.startsWith("fan-")) {
          const idx = parseInt(chId.split("-")[1], 10);
          if (idx >= 0 && idx < 8) {
            fanPayload[idx] = Math.min(1000, Math.max(0, manualPwm.fan[idx] * 10));
          }
        }
      });

      const payload = {
        pump: pumpPayload,
        fan: fanPayload,
      };
      const r = await fetch("/api/control/pwm", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await r.json();

      if (!r.ok) {
        const errMsg = data?.error || `HTTP ${r.status}`;
        alert(`${t("save_failed")}: ${errMsg}`);
        return;
      }

      // API success indicates values were saved to Redis and config.
      // data_crawler will apply to PCB on next poll cycle (~1 second).
      // Faster polling interval (500ms) will reflect changes quickly.
      alert("PWM saved. Applying to PCB...");
      setSelectedChannels(new Set());
      setInputValue("");
    } catch (err) {
      alert(`${t("save_failed")}: ${err?.message || err}`);
    } finally {
      setManualPwmSaving(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 min-h-screen bg-gray-100">
      <div className="flex flex-col lg:flex-row gap-5 items-start">

        {/* ══════════════════════════════════════
            LEFT SIDEBAR — System Configuration
        ══════════════════════════════════════ */}
        <div className="w-full lg:w-72 flex-shrink-0">
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label={t("section_system")} colorClass="bg-slate-800" />
            <div className="bg-white p-4 space-y-4">

              {/* Current IP */}
              <div>
                <p className="text-xs text-gray-400 mb-1">{t("current_ip")}</p>
                <p className="text-base font-bold text-gray-900">{currentIP}</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ethActive ? "bg-green-400" : "bg-red-400"}`} />
                  <span className="text-xs text-gray-400">
                    {ethActive ? t("eth0_active") : t("eth0_inactive")}
                  </span>
                </div>
              </div>

              {/* Server Select */}
              <div>
                <p className="text-xs text-gray-400 mb-2">{t("server")}</p>
                <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                  {SERVERS.map(({ label, value }) => (
                    <button
                      key={value}
                      onClick={() => handleServerChange(value)}
                      className={`flex-1 py-1.5 text-xs rounded-md font-bold uppercase tracking-wider transition-all ${
                        serverName === value
                          ? "bg-slate-800 text-white shadow"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Dashboard Link */}
              <a
                href={`http://${currentIP}/dashboard`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between w-full px-3 py-2 rounded-xl
                  bg-gradient-to-r from-orange-500 to-yellow-400
                  hover:from-orange-600 hover:to-yellow-500
                  text-white text-sm font-semibold shadow transition-all"
              >
                {t("open_dashboard")}
                <ArrowTopRightOnSquareIcon className="w-4 h-4" />
              </a>

              <hr className="border-gray-100" />

              {/* Network Mode */}
              <div>
                <p className="text-xs text-gray-400 mb-2">{t("network_mode")}</p>
                <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                  {["dhcp", "static"].map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setIPMode(mode)}
                      className={`flex-1 py-1.5 text-xs rounded-md font-bold uppercase tracking-wider transition-all ${
                        IPMode === mode
                          ? "bg-slate-800 text-white shadow"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              {/* Static IP Fields */}
              {IPMode === "static" && (
                <div className="space-y-2">
                  {[
                    { placeholder: t("ip_address"), refKey: "ip" },
                    { placeholder: t("prefix_length"), refKey: "netmask" },
                    { placeholder: t("gateway"), refKey: "gateway" },
                    { placeholder: t("dns1"), refKey: "dns1" },
                    { placeholder: t("dns2"), refKey: "dns2" },
                  ].map(({ placeholder, refKey }) => (
                    <input
                      key={refKey}
                      type="text"
                      placeholder={placeholder}
                      ref={(el) => (IPRefs.current[refKey] = el)}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                    />
                  ))}
                </div>
              )}

              {/* eth warning */}
              {!ethActive && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  {t("eth0_warning")}
                </p>
              )}

              {/* Update Button */}
              <button
                onClick={handleIPChange}
                disabled={loadingState.updateIP}
                className="flex items-center justify-center w-full px-4 py-2 bg-blue-500 text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-all disabled:opacity-50"
              >
                {loadingState.updateIP ? t("updating") : t("update_ip")}
                <CheckIcon className="w-4 h-4 ml-2" />
              </button>
            </div>
          </div>
        </div>

        {/* ══════════════════════════════════════
            RIGHT MAIN — LCD Control
        ══════════════════════════════════════ */}
        <div className="flex-1 min-w-0 space-y-3">
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 px-1">
            {t("section_lcd_control")}
          </p>

          {/* === General === */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label={t("section_general")} colorClass="bg-slate-700" />
            <div className="bg-white p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Display master */}
              <div className="flex sm:flex-col items-center sm:items-start justify-between sm:justify-start gap-2 bg-gray-50 rounded-xl p-3">
                <div>
                  <p className="text-sm font-semibold text-gray-800">{t("display")}</p>
                  <p className="text-xs text-gray-400">{t("display_master")}</p>
                </div>
                <Toggle
                  value={displayMode.display}
                  onChange={() =>
                    setDisplayMode((p) => ({ ...p, display: !p.display }))
                  }
                />
              </div>

              {/* Orientation */}
              <div className="flex sm:flex-col items-center sm:items-start justify-between sm:justify-start gap-2 bg-gray-50 rounded-xl p-3">
                <p className="text-sm font-semibold text-gray-800">{t("orientation")}</p>
                <div className="flex gap-1 bg-white rounded-lg p-1 shadow-sm border border-gray-100">
                  {[
                    { label: t("vertical"), value: "vertical", Icon: ArrowUpIcon },
                    { label: t("horizontal"), value: "horizontal", Icon: ArrowRightIcon },
                  ].map(({ label, value, Icon }) => (
                    <button
                      key={value}
                      onClick={() =>
                        setDisplayMode((p) => ({ ...p, orientation: value }))
                      }
                      className={`flex items-center gap-1 px-3 py-1 text-xs rounded-md font-bold transition-all ${
                        displayMode.orientation === value
                          ? "bg-slate-700 text-white shadow"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      <Icon className="w-3 h-3" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Rotation */}
              <div className="flex sm:flex-col items-center sm:items-start justify-between sm:justify-start gap-2 bg-gray-50 rounded-xl p-3">
                <div>
                  <p className="text-sm font-semibold text-gray-800">{t("rotation")}</p>
                  <p className="text-xs text-gray-400">{t("rotation_desc")}</p>
                </div>
                <div className="flex items-center gap-2 bg-white rounded-lg px-3 py-1.5 shadow-sm border border-gray-100">
                  <input
                    type="number"
                    min={1}
                    value={displayMode.rotationTime}
                    onChange={(e) => {
                      const value = Math.floor(Number(e.target.value));
                      setDisplayMode((p) => ({
                        ...p,
                        rotationTime: value < 1 ? 1 : value,
                      }));
                    }}
                    className="w-10 text-center text-sm font-bold focus:outline-none bg-transparent text-gray-800"
                  />
                  <span className="text-xs text-gray-400">{t("sec_unit")}</span>
                </div>
              </div>
            </div>
          </div>

          {/* === Hardware Count === */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label={t("section_hardware_count")} colorClass="bg-gray-600" />
            <div className="bg-white p-4 grid grid-cols-3 gap-4">
              {[
                { label: t("gpu_count"), key: "gpuCount", min: 0, max: 10 },
                { label: t("cpu_count"), key: "cpuCount", min: 1, max: 4 },
                { label: "NVMe", key: "nvmeCount", min: 0, max: 32 },
              ].map(({ label, key, min, max }) => (
                <div key={key} className="flex sm:flex-col items-center sm:items-start justify-between sm:justify-start gap-2 bg-gray-50 rounded-xl p-3">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{label}</p>
                    <p className="text-xs text-gray-400">
                      config.ini {key === "gpuCount" ? "gpu_count" : key === "cpuCount" ? "cpu_count" : "nvme_count"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 bg-white rounded-lg px-3 py-1.5 shadow-sm border border-gray-100">
                    <input
                      type="number"
                      min={min}
                      max={max}
                      value={displayMode[key]}
                      onChange={(e) => {
                        const value = Math.floor(Number(e.target.value));
                        setDisplayMode((p) => ({
                          ...p,
                          [key]: Math.max(min, Math.min(max, value)),
                        }));
                      }}
                      className="w-10 text-center text-sm font-bold focus:outline-none bg-transparent text-gray-800"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* === Compute + Cooling side by side === */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Compute */}
            <div className="rounded-2xl overflow-hidden shadow-sm">
              <SectionHeader label={t("section_compute")} colorClass="bg-blue-600" />
              <div className="bg-blue-50/60 p-3 grid grid-cols-3 gap-2">
                {[
                  { label: t("cpu"), key: "cpu" },
                  { label: t("gpu"), key: "gpu" },
                  { label: t("memory"), key: "memory" },
                ].map(({ label, key }) => (
                  <GridCard
                    key={key}
                    label={label}
                    stateKey={key}
                    displayMode={displayMode}
                    setDisplayMode={setDisplayMode}
                    activeClass="bg-blue-100 border border-blue-300 text-blue-800"
                  />
                ))}
              </div>
            </div>

            {/* Cooling & Chassis */}
            <div className="rounded-2xl overflow-hidden shadow-sm">
              <SectionHeader label={t("section_cooling_chassis")} colorClass="bg-teal-600" />
              <div className="bg-teal-50/60 p-3 grid grid-cols-2 gap-2">
                {[
                  { label: t("chassis"), key: "chassis" },
                  { label: t("coolant"), key: "coolant" },
                  { label: t("coolant_detail"), key: "coolant_detail" },
                  { label: t("coolant_flow"), key: "coolant_flow" },
                  { label: t("fan_rpm"), key: "fan_rpm" },
                  { label: "NVMe", key: "nvme" },
                  { label: t("leak"), key: "leak" },
                ].map(({ label, key }) => (
                  <GridCard
                    key={key}
                    label={label}
                    stateKey={key}
                    displayMode={displayMode}
                    setDisplayMode={setDisplayMode}
                    activeClass="bg-teal-100 border border-teal-300 text-teal-800"
                  />
                ))}
              </div>
            </div>
          </div>

          {/* === Daily Graphs === */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label={t("section_daily_graphs")} colorClass="bg-violet-600" />
            <div className="bg-violet-50/60 p-3 grid grid-cols-3 gap-2">
              {[
                { label: t("cpu_daily"), key: "cpu_daily" },
                { label: t("gpu_daily"), key: "gpu_daily" },
                { label: t("coolant_daily"), key: "coolant_daily" },
              ].map(({ label, key }) => (
                <GridCard
                  key={key}
                  label={label}
                  stateKey={key}
                  displayMode={displayMode}
                  setDisplayMode={setDisplayMode}
                  activeClass="bg-violet-100 border border-violet-300 text-violet-800"
                />
              ))}
            </div>
          </div>

          {/* Apply */}
          <div className="flex justify-end pt-1">
            <button
              onClick={handleDisplayMode}
              disabled={loadingState.applyDisplayConfig}
              className="inline-flex items-center justify-center h-10 px-6 bg-slate-800 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 transition-all disabled:opacity-50"
            >
              {loadingState.applyDisplayConfig ? (
                <LoadingSpinner color={"white"} />
              ) : (
                <>
                  <CheckIcon className="w-4 h-4 mr-2" />
                  {t("apply")}
                </>
              )}
            </button>
          </div>

          {/* ══════════════════════════════════════
              Control Board
          ══════════════════════════════════════ */}
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 px-1 pt-3">
            {t("section_control_board")}
          </p>

          {/* === Status + Mode === */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label={t("section_pcb_status")} colorClass="bg-emerald-700" />
            <div className="bg-white p-4 flex flex-wrap items-center gap-x-6 gap-y-3">
              {/* PCB Modbus communication status */}
              <div className="flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    cbStatus.pcb_connected ? "bg-green-400" : "bg-amber-400"
                  }`}
                />
                <span className="text-sm font-semibold text-gray-800">
                  {cbStatus.pcb_connected
                    ? t("pcb_connected")
                    : cbStatus.comm_status === "timeout"
                    ? t("pcb_timeout")
                    : t("pcb_disconnected")}
                </span>
                <span className="text-xs text-gray-400 font-mono">
                  comm: {cbStatus.comm_status}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 uppercase tracking-wider">{t("mode")}</span>
                <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="cb-mode"
                    checked={pendingMode === "auto"}
                    onChange={() => setPendingMode("auto")}
                    disabled={!cbStatus.pcb_connected || modeSaving}
                  />
                  {t("auto")}
                </label>
                <label className="flex items-center gap-1.5 text-sm cursor-not-allowed opacity-50">
                  <input
                    type="radio"
                    name="cb-mode"
                    checked={pendingMode === "manual"}
                    onChange={() => setPendingMode("manual")}
                    disabled={true}
                  />
                  {t("manual")} (disabled)
                </label>
                {(() => {
                  const dirty = pendingMode !== cbStatus.mode;
                  const enabled = dirty && cbStatus.pcb_connected && !modeSaving;
                  return (
                    <button
                      onClick={() => handleModeChange(pendingMode)}
                      disabled={!enabled}
                      className={`inline-flex items-center justify-center h-8 px-4 text-xs font-semibold rounded-lg transition-all ${
                        (dirty || modeSaving) && cbStatus.pcb_connected
                          ? "bg-emerald-600 text-white hover:bg-emerald-700"
                          : "bg-gray-200 text-gray-400 cursor-not-allowed"
                      }`}
                    >
                      {modeSaving ? (
                        <LoadingSpinner color={"white"} />
                      ) : (
                        <>
                          <CheckIcon className="w-3.5 h-3.5 mr-1" />
                          {t("save")}
                        </>
                      )}
                    </button>
                  );
                })()}
              </div>
              {!cbStatus.pcb_connected && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1">
                  {t("pcb_unreachable_warning")}
                </p>
              )}
            </div>
          </div>

          {/* === PWM Duty (read-only) === */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label={t("section_pwm_duty")} colorClass="bg-emerald-600" />
            <div className="bg-emerald-50/60 p-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl p-3">
                <p className="text-xs text-gray-500 mb-2 font-bold uppercase tracking-wider">
                  {t("pumps_label")}
                </p>
                <div className="space-y-1">
                  {cbPwm.pump.map((duty, i) => (
                    <div key={`pump-${i}`} className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1.5">
                        <span className="text-gray-600 font-mono">CH{i + 1}</span>
                        {!cbPwm.curvePump?.includes(i + 1) && (
                          <span className="text-[9px] uppercase tracking-wider px-1 py-0.5 rounded bg-gray-100 text-gray-400 border border-gray-200">
                            {t("pwm_fixed")}
                          </span>
                        )}
                      </span>
                      <span className="font-mono">
                        {duty === null ? (
                          <span className="text-gray-300">—</span>
                        ) : (
                          <>
                            {duty}{" "}
                            <span className="text-xs text-gray-400">
                              ({(duty / 10).toFixed(1)}%)
                            </span>
                          </>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Estimated pump flow — based on duty + topology multiplier (config.yaml § pump). */}
                <div className="mt-3 pt-2 border-t border-gray-100 flex items-center justify-between text-sm">
                  <span className="text-gray-500 text-xs uppercase tracking-wider">
                    {t("estimated_flow")}
                  </span>
                  <span className="font-mono">
                    {cbPwm.coolantFlowLpm === null ? (
                      <span className="text-gray-300">—</span>
                    ) : (
                      <>
                        {cbPwm.coolantFlowLpm.toFixed(1)}{" "}
                        <span className="text-xs text-gray-400">L/min</span>
                      </>
                    )}
                  </span>
                </div>
              </div>
              <div className="bg-white rounded-xl p-3">
                <p className="text-xs text-gray-500 mb-2 font-bold uppercase tracking-wider">
                  {t("fans_label")}
                </p>
                <div className="space-y-1">
                  {cbPwm.fan.map((duty, i) => (
                    <div key={`fan-${i}`} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 text-sm">
                      <span className="flex items-center gap-1.5">
                        <span className="text-gray-600 font-mono">CH{i + 5}</span>
                        {!cbPwm.curveFan?.includes(i + 5) && (
                          <span className="text-[9px] uppercase tracking-wider px-1 py-0.5 rounded bg-gray-100 text-gray-400 border border-gray-200">
                            {t("pwm_fixed")}
                          </span>
                        )}
                      </span>
                      <span className="font-mono text-right">
                        {duty === null ? (
                          <span className="text-gray-300">—</span>
                        ) : (
                          <>
                            {duty}{" "}
                            <span className="text-xs text-gray-400">
                              ({(duty / 10).toFixed(1)}%)
                            </span>
                          </>
                        )}
                      </span>
                      <span className="font-mono text-right text-gray-600 min-w-[5.5rem]">
                        {cbPwm.fanRpm[i] === null || cbPwm.fanRpm[i] === undefined ? (
                          <span className="text-gray-300">—</span>
                        ) : (
                          <>
                            {cbPwm.fanRpm[i]}{" "}
                            <span className="text-xs text-gray-400">rpm</span>
                          </>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* === Manual PWM (show only in manual mode) === */}
          {cbStatus.mode === "manual" && (
            <div className="rounded-2xl overflow-hidden shadow-sm">
              <SectionHeader label={t("manual_pwm_title") || "Manual PWM Control"} colorClass="bg-emerald-600" />
              <div className="bg-white p-4">
                <p className="text-xs text-gray-500 mb-4">
                  {t("manual_pwm_desc") || "Select channels and set PWM duty (0-100%)"}
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
                  {/* Pump Channel Selection */}
                  <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                    <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">
                      {t("pumps_label")}
                    </h5>
                    <div className="space-y-2">
                      {manualPwm.pump.map((duty, i) => {
                        const chId = `pump-${i}`;
                        const isSelected = selectedChannels.has(chId);
                        return (
                          <label key={chId} className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                            isSelected ? "bg-emerald-100 border border-emerald-300" : "hover:bg-gray-100"
                          }`}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                const newSelected = new Set(selectedChannels);
                                if (e.target.checked) {
                                  newSelected.add(chId);
                                } else {
                                  newSelected.delete(chId);
                                }
                                setSelectedChannels(newSelected);
                              }}
                              disabled={!cbStatus.pcb_connected}
                              className="w-4 h-4"
                            />
                            <span className="flex-1 text-xs text-gray-600 font-mono">CH{i + 1}</span>
                            <span className="text-xs text-gray-500">Current:</span>
                            <span className="text-xs font-mono text-gray-700 min-w-12 text-right">
                              {duty}%
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  {/* Fan Channel Selection */}
                  <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                    <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">
                      {t("fans_label")}
                    </h5>
                    <div className="space-y-2">
                      {manualPwm.fan.map((duty, i) => {
                        const chId = `fan-${i}`;
                        const isSelected = selectedChannels.has(chId);
                        return (
                          <label key={chId} className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                            isSelected ? "bg-emerald-100 border border-emerald-300" : "hover:bg-gray-100"
                          }`}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                const newSelected = new Set(selectedChannels);
                                if (e.target.checked) {
                                  newSelected.add(chId);
                                } else {
                                  newSelected.delete(chId);
                                }
                                setSelectedChannels(newSelected);
                              }}
                              disabled={!cbStatus.pcb_connected}
                              className="w-4 h-4"
                            />
                            <span className="flex-1 text-xs text-gray-600 font-mono">CH{i + 5}</span>
                            <span className="text-xs text-gray-500">Current:</span>
                            <span className="text-xs font-mono text-gray-700 min-w-12 text-right">
                              {duty}%
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Value Input Section */}
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-4">
                  <p className="text-xs text-gray-600 mb-3">
                    <span className="font-semibold">
                      {selectedChannels.size === 0 ? "Select channels to modify" : `${selectedChannels.size} channel(s) selected`}
                    </span>
                  </p>
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={inputValue}
                      onChange={(e) => {
                        const value = e.target.value;
                        setInputValue(value);

                        // Apply to selected channels in real-time
                        if (selectedChannels.size > 0 && value !== "") {
                          const numValue = Math.max(0, Math.min(100, parseInt(value, 10) || 0));
                          setManualPwm((prevState) => {
                            const newPump = [...prevState.pump];
                            const newFan = [...prevState.fan];

                            selectedChannels.forEach((chId) => {
                              if (chId.startsWith("pump-")) {
                                const idx = parseInt(chId.split("-")[1], 10);
                                if (idx >= 0 && idx < 4) {
                                  newPump[idx] = numValue;
                                }
                              } else if (chId.startsWith("fan-")) {
                                const idx = parseInt(chId.split("-")[1], 10);
                                if (idx >= 0 && idx < 8) {
                                  newFan[idx] = numValue;
                                }
                              }
                            });

                            return { pump: newPump, fan: newFan };
                          });
                        }
                      }}
                      disabled={!cbStatus.pcb_connected || selectedChannels.size === 0}
                      className="flex-1 border border-emerald-300 rounded-lg px-3 py-2 text-sm font-mono bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-100 disabled:text-gray-400"
                      placeholder="0-100"
                    />
                    <span className="text-sm font-semibold text-emerald-700">%</span>
                  </div>
                </div>

                <div className="flex justify-end items-center pt-1">
                  <button
                    disabled={!cbStatus.pcb_connected || manualPwmSaving}
                    onClick={handleManualPwmSave}
                    className="inline-flex items-center justify-center h-9 px-5 bg-emerald-700 text-white text-sm font-semibold rounded-xl hover:bg-emerald-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {manualPwmSaving ? (
                      <LoadingSpinner color={"white"} />
                    ) : (
                      <>
                        <CheckIcon className="w-4 h-4 mr-2" />
                        {t("save")}
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* === Fan Curve editor (show only in auto mode) === */}
          {cbStatus.mode === "auto" && (
            <div className="rounded-2xl overflow-hidden shadow-sm">
              <SectionHeader label={t("fan_curve_title")} colorClass="bg-emerald-500" />
            <div className="bg-white p-4">
              {fanCurveLoading ? (
                <p className="text-sm text-gray-400">{t("loading")}</p>
              ) : (
                <>
                  <p className="text-xs text-gray-500 mb-4">{t("fan_curve_desc")}</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {/* Idle pair */}
                    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />
                        <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                          {t("idle_group")}
                        </h5>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <label className="flex flex-col gap-1">
                          <span className="text-[10px] text-gray-500 font-semibold uppercase">
                            {t("idle_temp")}
                          </span>
                          <input
                            type="number"
                            step="1"
                            min={0}
                            max={100}
                            disabled={!cbStatus.active}
                            value={fanCurve.min_temp}
                            onChange={(e) =>
                              setFanCurve((p) => ({
                                ...p,
                                min_temp: Number(e.target.value),
                              }))
                            }
                            className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                          />
                        </label>
                        <label className="flex flex-col gap-1">
                          <span className="text-[10px] text-gray-500 font-semibold uppercase">
                            {t("idle_pwm")}
                          </span>
                          <input
                            type="number"
                            step="1"
                            min={0}
                            max={100}
                            disabled={!cbStatus.active}
                            value={Math.round(fanCurve.min_duty / 10)}
                            onChange={(e) =>
                              setFanCurve((p) => ({
                                ...p,
                                min_duty: Math.max(0, Math.min(1000, Number(e.target.value) * 10)),
                              }))
                            }
                            className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                          />
                        </label>
                      </div>
                    </div>
                    {/* Warning pair */}
                    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="inline-block w-2 h-2 rounded-full bg-rose-400" />
                        <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                          {t("warning_group")}
                        </h5>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <label className="flex flex-col gap-1">
                          <span className="text-[10px] text-gray-500 font-semibold uppercase">
                            {t("warning_temp")}
                          </span>
                          <input
                            type="number"
                            step="1"
                            min={0}
                            max={100}
                            disabled={!cbStatus.active}
                            value={fanCurve.max_temp}
                            onChange={(e) =>
                              setFanCurve((p) => ({
                                ...p,
                                max_temp: Number(e.target.value),
                              }))
                            }
                            className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                          />
                        </label>
                        <label className="flex flex-col gap-1">
                          <span className="text-[10px] text-gray-500 font-semibold uppercase">
                            {t("max_pwm")}
                          </span>
                          <input
                            type="number"
                            step="1"
                            min={0}
                            max={100}
                            disabled={!cbStatus.active}
                            value={Math.round(fanCurve.max_duty / 10)}
                            onChange={(e) =>
                              setFanCurve((p) => ({
                                ...p,
                                max_duty: Math.max(0, Math.min(1000, Number(e.target.value) * 10)),
                              }))
                            }
                            className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                          />
                        </label>
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-end items-center pt-1">
                    <button
                      disabled={!cbStatus.active || fanCurveSaving}
                      onClick={handleFanCurveSave}
                      title={!cbStatus.active ? t("service_inactive_tooltip") : ""}
                      className="inline-flex items-center justify-center h-9 px-5 bg-emerald-700 text-white text-sm font-semibold rounded-xl hover:bg-emerald-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {fanCurveSaving ? (
                        <LoadingSpinner color={"white"} />
                      ) : (
                        <>
                          <CheckIcon className="w-4 h-4 mr-2" />
                          {t("save")}
                        </>
                      )}
                    </button>
                  </div>
                </>
              )}
            </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
