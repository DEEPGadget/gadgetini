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
  const [currentIP, setCurrentIP] = useState("localhost");
  const [ethActive, setEthActive] = useState(false);
  const [serverName, setServerName] = useState("dg5r");
  const [displayMode, setDisplayMode] = useState({
    orientation: "vertical",
    display: true,
    coolant: false,
    coolant_detail: true,
    chassis: true,
    cpu: true,
    gpu: true,
    memory: true,
    coolant_daily: true,
    gpu_daily: true,
    cpu_daily: true,
    psu: false,
    leak: true,
    rotationTime: 7,
    gpuCount: 8,
    cpuCount: 2,
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

  // ── Control Board state ──
  const [cbStatus, setCbStatus] = useState({ active: false, mode: "auto" });
  const [cbPwm, setCbPwm] = useState({
    pump: [null, null, null, null],
    fan: [null, null, null, null, null, null, null, null],
  });
  const [fanCurve, setFanCurve] = useState({ hysteresis_c: 1.0, stages: [] });
  const [fanCurveLoading, setFanCurveLoading] = useState(true);
  const [fanCurveSaving, setFanCurveSaving] = useState(false);

  useEffect(() => {
    getDisplayConfig().then(setDisplayMode);
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
    if (!window.confirm("Are you sure you want to change the IP?")) {
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
        alert(`Failed to update IP \n ${message.error}`);
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
        alert(`Failed to update config \n ${message.error}`);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoadingState({ ...loadingState, applyDisplayConfig: false });
    }
  };

  // ── Control Board polls ──
  // Status: 5s cadence — service active 여부 확인 (systemctl is-active)
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

  // PWM duty readback: 2s cadence — pump CH1~4 + fan CH5~12
  useEffect(() => {
    const fetchPwm = () =>
      fetch("/api/control/pwm")
        .then((r) => r.json())
        .then((d) => {
          if (d && Array.isArray(d.pump) && Array.isArray(d.fan)) setCbPwm(d);
        })
        .catch(() => {});
    fetchPwm();
    const id = setInterval(fetchPwm, 2000);
    return () => clearInterval(id);
  }, []);

  // fan_curve: 최초 1회만 fetch (편집 중 외부 변경 덮어쓰지 않도록)
  useEffect(() => {
    setFanCurveLoading(true);
    fetch("/api/control/fan-curve")
      .then((r) => r.json())
      .then((d) => {
        if (d && Array.isArray(d.stages)) setFanCurve(d);
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
        alert(`Failed to save fan curve: ${e.error || r.status}`);
      }
    } catch (err) {
      alert(`Failed to save fan curve: ${err?.message || err}`);
    } finally {
      setFanCurveSaving(false);
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
            <SectionHeader label="System" colorClass="bg-slate-800" />
            <div className="bg-white p-4 space-y-4">

              {/* Current IP */}
              <div>
                <p className="text-xs text-gray-400 mb-1">Current IP</p>
                <p className="text-base font-bold text-gray-900">{currentIP}</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ethActive ? "bg-green-400" : "bg-red-400"}`} />
                  <span className="text-xs text-gray-400">
                    {ethActive ? "eth0 active" : "eth0 not detected"}
                  </span>
                </div>
              </div>

              {/* Server Select */}
              <div>
                <p className="text-xs text-gray-400 mb-2">Server</p>
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
                Open Dashboard
                <ArrowTopRightOnSquareIcon className="w-4 h-4" />
              </a>

              <hr className="border-gray-100" />

              {/* Network Mode */}
              <div>
                <p className="text-xs text-gray-400 mb-2">Network Mode</p>
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
                    { placeholder: "IP Address", refKey: "ip" },
                    { placeholder: "Prefix Length (e.g. 24)", refKey: "netmask" },
                    { placeholder: "Gateway", refKey: "gateway" },
                    { placeholder: "DNS 1 (optional)", refKey: "dns1" },
                    { placeholder: "DNS 2 (optional)", refKey: "dns2" },
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
                  ⚠ eth0 not connected — IP update unavailable
                </p>
              )}

              {/* Update Button */}
              <button
                onClick={handleIPChange}
                disabled={loadingState.updateIP}
                className="flex items-center justify-center w-full px-4 py-2 bg-blue-500 text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-all disabled:opacity-50"
              >
                {loadingState.updateIP ? "Updating..." : "Update IP"}
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
            LCD Control
          </p>

          {/* ── General ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label="General" colorClass="bg-slate-700" />
            <div className="bg-white p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Display master */}
              <div className="flex sm:flex-col items-center sm:items-start justify-between sm:justify-start gap-2 bg-gray-50 rounded-xl p-3">
                <div>
                  <p className="text-sm font-semibold text-gray-800">Display</p>
                  <p className="text-xs text-gray-400">LCD master on/off</p>
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
                <p className="text-sm font-semibold text-gray-800">Orientation</p>
                <div className="flex gap-1 bg-white rounded-lg p-1 shadow-sm border border-gray-100">
                  {[
                    { label: "Vertical", value: "vertical", Icon: ArrowUpIcon },
                    { label: "Horizontal", value: "horizontal", Icon: ArrowRightIcon },
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
                  <p className="text-sm font-semibold text-gray-800">Rotation</p>
                  <p className="text-xs text-gray-400">Panel switch interval</p>
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
                  <span className="text-xs text-gray-400">sec</span>
                </div>
              </div>
            </div>
          </div>

          {/* ── Hardware Count ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label="Hardware Count" colorClass="bg-gray-600" />
            <div className="bg-white p-4 grid grid-cols-2 gap-4">
              {[
                { label: "GPU Count", key: "gpuCount", min: 0, max: 8 },
                { label: "CPU Count", key: "cpuCount", min: 1, max: 4 },
              ].map(({ label, key, min, max }) => (
                <div key={key} className="flex sm:flex-col items-center sm:items-start justify-between sm:justify-start gap-2 bg-gray-50 rounded-xl p-3">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{label}</p>
                    <p className="text-xs text-gray-400">config.ini {key === "gpuCount" ? "gpu_count" : "cpu_count"}</p>
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

          {/* ── Compute + Cooling side by side ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Compute */}
            <div className="rounded-2xl overflow-hidden shadow-sm">
              <SectionHeader label="Compute" colorClass="bg-blue-600" />
              <div className="bg-blue-50/60 p-3 grid grid-cols-3 gap-2">
                {[
                  { label: "CPU", key: "cpu" },
                  { label: "GPU", key: "gpu" },
                  { label: "Memory", key: "memory" },
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
              <SectionHeader label="Cooling & Chassis" colorClass="bg-teal-600" />
              <div className="bg-teal-50/60 p-3 grid grid-cols-2 gap-2">
                {[
                  { label: "Chassis", key: "chassis" },
                  { label: "Coolant", key: "coolant" },
                  { label: "Coolant Detail", key: "coolant_detail" },
                  { label: "Leak", key: "leak" },
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

          {/* ── Daily Graphs ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label="Daily Graphs" colorClass="bg-violet-600" />
            <div className="bg-violet-50/60 p-3 grid grid-cols-3 gap-2">
              {[
                { label: "CPU Daily", key: "cpu_daily" },
                { label: "GPU Daily", key: "gpu_daily" },
                { label: "Coolant Daily", key: "coolant_daily" },
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
                  Apply
                </>
              )}
            </button>
          </div>

          {/* ══════════════════════════════════════
              Control Board
          ══════════════════════════════════════ */}
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 px-1 pt-3">
            Control Board
          </p>

          {/* ── Status + Mode ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label="PCB Status" colorClass="bg-emerald-700" />
            <div className="bg-white p-4 flex flex-wrap items-center gap-x-6 gap-y-3">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    cbStatus.active ? "bg-green-400" : "bg-red-400"
                  }`}
                />
                <span className="text-sm font-semibold text-gray-800">
                  {cbStatus.active ? "Active" : "Inactive"}
                </span>
                <span className="text-xs text-gray-400">
                  control_board.service
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 uppercase tracking-wider">Mode</span>
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" name="cb-mode" checked readOnly />
                  Auto
                </label>
                <label
                  className="flex items-center gap-1.5 text-sm text-gray-300 cursor-not-allowed"
                  title="TBD — Manual mode not yet implemented"
                >
                  <input type="radio" name="cb-mode" disabled />
                  Manual <span className="text-[10px]">(TBD)</span>
                </label>
              </div>
              {!cbStatus.active && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1">
                  ⚠ Service inactive — controls disabled
                </p>
              )}
            </div>
          </div>

          {/* ── PWM Duty (read-only) ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label="PWM Duty (read-only)" colorClass="bg-emerald-600" />
            <div className="bg-emerald-50/60 p-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl p-3">
                <p className="text-xs text-gray-500 mb-2 font-bold uppercase tracking-wider">
                  Pumps · CH 1~4
                </p>
                <div className="space-y-1">
                  {cbPwm.pump.map((duty, i) => (
                    <div key={`pump-${i}`} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 font-mono">CH{i + 1}</span>
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
              </div>
              <div className="bg-white rounded-xl p-3">
                <p className="text-xs text-gray-500 mb-2 font-bold uppercase tracking-wider">
                  Fans · CH 5~12
                </p>
                <div className="space-y-1">
                  {cbPwm.fan.map((duty, i) => (
                    <div key={`fan-${i}`} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 font-mono">CH{i + 5}</span>
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
              </div>
            </div>
          </div>

          {/* ── Fan Curve editor ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm">
            <SectionHeader label="Fan Curve (Auto)" colorClass="bg-emerald-500" />
            <div className="bg-white p-4">
              {fanCurveLoading ? (
                <p className="text-sm text-gray-400">Loading...</p>
              ) : (
                <>
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-xs text-gray-500 font-bold uppercase tracking-wider">
                      Hysteresis (°C)
                    </span>
                    <input
                      type="number"
                      step="0.1"
                      min={0}
                      max={10}
                      disabled={!cbStatus.active}
                      value={fanCurve.hysteresis_c}
                      onChange={(e) =>
                        setFanCurve((p) => ({
                          ...p,
                          hysteresis_c: Number(e.target.value) || 0,
                        }))
                      }
                      className="w-20 border border-gray-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                    />
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-gray-500 border-b uppercase tracking-wider">
                        <th className="text-left py-2 font-bold">Until Outlet (°C)</th>
                        <th className="text-left py-2 font-bold">Duty (0~1000)</th>
                        <th className="text-left py-2 font-bold">%</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {fanCurve.stages.map((s, i) => (
                        <tr key={i} className="border-b last:border-b-0">
                          <td className="py-2">
                            <input
                              type="number"
                              disabled={!cbStatus.active}
                              value={s.until_outlet ?? ""}
                              placeholder="(ceiling)"
                              onChange={(e) => {
                                const v = e.target.value === "" ? null : Number(e.target.value);
                                setFanCurve((p) => ({
                                  ...p,
                                  stages: p.stages.map((x, j) =>
                                    j === i ? { ...x, until_outlet: v } : x
                                  ),
                                }));
                              }}
                              className="w-24 border border-gray-200 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                            />
                          </td>
                          <td className="py-2">
                            <input
                              type="number"
                              min={0}
                              max={1000}
                              disabled={!cbStatus.active}
                              value={s.duty}
                              onChange={(e) => {
                                const v = Number(e.target.value);
                                setFanCurve((p) => ({
                                  ...p,
                                  stages: p.stages.map((x, j) =>
                                    j === i ? { ...x, duty: v } : x
                                  ),
                                }));
                              }}
                              className="w-24 border border-gray-200 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:bg-gray-50 disabled:text-gray-400"
                            />
                          </td>
                          <td className="py-2 text-xs text-gray-500 font-mono">
                            {(s.duty / 10).toFixed(1)}%
                          </td>
                          <td className="py-2 text-right">
                            <button
                              disabled={!cbStatus.active || fanCurve.stages.length <= 1}
                              onClick={() =>
                                setFanCurve((p) => ({
                                  ...p,
                                  stages: p.stages.filter((_, j) => j !== i),
                                }))
                              }
                              className="text-xs text-red-500 hover:text-red-700 disabled:text-gray-300 disabled:cursor-not-allowed"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="flex justify-between items-center pt-3">
                    <button
                      disabled={!cbStatus.active}
                      onClick={() =>
                        setFanCurve((p) => ({
                          ...p,
                          stages: [...p.stages, { until_outlet: null, duty: 1000 }],
                        }))
                      }
                      className="text-xs px-3 py-1.5 border border-emerald-300 rounded-lg text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      + Add Stage
                    </button>
                    <button
                      disabled={!cbStatus.active || fanCurveSaving}
                      onClick={handleFanCurveSave}
                      title={!cbStatus.active ? "control_board.service is inactive" : ""}
                      className="inline-flex items-center justify-center h-9 px-5 bg-emerald-700 text-white text-sm font-semibold rounded-xl hover:bg-emerald-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {fanCurveSaving ? (
                        <LoadingSpinner color={"white"} />
                      ) : (
                        <>
                          <CheckIcon className="w-4 h-4 mr-2" />
                          Save
                        </>
                      )}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
