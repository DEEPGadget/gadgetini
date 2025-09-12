"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  ArrowUpIcon,
  ArrowRightIcon,
  CheckIcon,
  ArrowTopRightOnSquareIcon,
} from "@heroicons/react/24/solid";
import LoadingSpinner from "../utils/LoadingSpinner";
import { getSelfIP } from "../utils/ip/getSelfIP";
import { getDisplayConfig } from "../utils/display/getDisplayConfig";

export default function Settings() {
  // Current IP Info
  const [currentIP, setCurrentIP] = useState("localhost");

  // Display Config Info
  const [displayMode, setDisplayMode] = useState({
    orientation: "vertical",
    chassis: true,
    cpu: false,
    gpu: false,
    memory: false,
    psu: false,
    rotationTime: 5,
    display: true,
  });

  // Input IP Config Info
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

  // Loading Info
  const [loadingState, setLoadingState] = useState({
    updateIP: false,
    applyDisplayConfig: false,
  });

  // API: Get current IP and display config
  useEffect(() => {
    getDisplayConfig().then(setDisplayMode);
    getSelfIP().then(setCurrentIP);
  }, []);

  // API: Handle IP Update
  const handleIPChange = async () => {
    setLoadingState({ ...loadingState, updateIP: true });
    if (!window.confirm("Are you sure you want to change the IP?")) {
      return;
    }
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

  // API: Handle Display Config Update
  const handleDisplayMode = async () => {
    setLoadingState({ ...loadingState, applyDisplayConfig: true });
    try {
      const response = await fetch("/api/display-config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
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

  // FE: Toggle display config
  const toggleStatus = (key) => {
    const targetKey = key === "On/Off" ? "display" : key.toLowerCase();

    setDisplayMode((prev) => ({
      ...prev,
      [targetKey]: !prev[targetKey],
    }));
  };

  return (
    <div className="p-4">
      {/* System Configuration */}
      <div className="mb-6">
        <h2 className="text-xl font-bold">System Configuration</h2>

        {/* Display Current IP & Dashboard */}
        <div className="flex flex-col gap-3 mt-4">
          <div className="flex items-center flex-wrap gap-4">
            <p className="text-base">
              Current Gadgetini IP : <strong>{currentIP}</strong>
            </p>
            <a
              href={`http://${currentIP}/dashboard`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-3 py-2 text-white rounded-lg transition-all 
                bg-gradient-to-br from-orange-600 to-yellow-500 hover:from-orange-700 hover:to-yellow-600 
                shadow-md hover:shadow-lg text-sm md:text-base"
            >
              Dashboard
              <ArrowTopRightOnSquareIcon className="w-4 h-4 md:w-5 md:h-5 ml-2" />
            </a>
          </div>
        </div>

        {/* Set Gadgetini IP */}
        <div className="flex flex-col gap-3 mt-4">
          <div className="flex items-center flex-wrap gap-4">
            <p className="text-base">Set Gadgetini IP :</p>
            <div className="flex items-center gap-4">
              <label className="flex items-center space-x-2">
                <input
                  type="radio"
                  value="dhcp"
                  checked={IPMode === "dhcp"}
                  onChange={() => setIPMode("dhcp")}
                  className="w-4 h-4 text-blue-500"
                />
                <span>DHCP</span>
              </label>
              <label className="flex items-center space-x-2">
                <input
                  type="radio"
                  value="static"
                  checked={IPMode === "static"}
                  onChange={() => setIPMode("static")}
                  className="w-4 h-4 text-blue-500"
                />
                <span>Static</span>
              </label>
            </div>
            {IPMode === "static" && (
              <div className="flex flex-wrap gap-2 mt-2">
                <input
                  type="text"
                  placeholder="Gadgetini IP Address"
                  ref={(el) => (IPRefs.current.ip = el)}
                  className="border p-2 rounded w-42 text-left"
                />
                <input
                  type="text"
                  placeholder="Netmask"
                  ref={(el) => (IPRefs.current.netmask = el)}
                  className="border p-2 rounded w-36 text-left"
                />
                <input
                  type="text"
                  placeholder="Gateway"
                  ref={(el) => (IPRefs.current.gateway = el)}
                  className="border p-2 rounded w-36 text-left"
                />
                <input
                  type="text"
                  placeholder="DNS 1 (Option)"
                  ref={(el) => (IPRefs.current.dns1 = el)}
                  className="border p-2 rounded w-36 text-left"
                />
                <input
                  type="text"
                  placeholder="DNS 2 (Option)"
                  ref={(el) => (IPRefs.current.dns2 = el)}
                  className="border p-2 rounded w-36 text-left"
                />
              </div>
            )}
            <button
              onClick={handleIPChange}
              className="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all"
              disabled={loadingState.updateIP}
            >
              {loadingState.updateIP ? "Updating..." : "Update"}
              <CheckIcon className="w-5 h-5 ml-2" />
            </button>
          </div>

          {IPMode === "static" && (
            <div className="flex flex-wrap gap-2 mt-2"></div>
          )}
        </div>
      </div>

      {/* LCD Control */}
      <h2 className="text-xl font-bold mb-3">LCD Control</h2>

      {/* Desktop Table */}
      <table className="hidden md:table w-full bg-white border-separate border-spacing-0 table-auto">
        <thead>
          <tr className="border-b-2 border-gray-400">
            <th className="py-2 px-4 border border-gray-300 text-center w-auto">
              Info
            </th>
            <th className="py-2 px-4 border border-gray-300 text-center w-full">
              Description
            </th>
            <th className="py-2 px-4 border border-gray-300 text-center w-auto">
              Status / Control
            </th>
          </tr>
        </thead>
        <tbody>
          {/* Orientation Row */}
          <tr className="border-b border-gray-300">
            <td className="py-2 px-4 border border-gray-300 text-center">
              Orientation
            </td>
            <td className="py-2 px-4 border border-gray-300 ">
              Determines the display output orientation.
            </td>
            <td className="py-2 px-4 border border-gray-300 flex justify-center gap-2">
              <button
                onClick={() =>
                  setDisplayMode((prev) => ({
                    ...prev,
                    orientation: "vertical",
                  }))
                }
                className={`flex items-center bg-green-500 text-white p-2 rounded-lg hover:bg-green-600 transition-all ${
                  displayMode.orientation === "vertical"
                    ? "border-2 border-black"
                    : ""
                }`}
              >
                <ArrowUpIcon className="w-5 h-5 mr-1" />
                Vertical
              </button>
              <button
                onClick={() =>
                  setDisplayMode((prev) => ({
                    ...prev,
                    orientation: "horizontal",
                  }))
                }
                className={`flex items-center bg-green-500 text-white p-2 rounded-lg hover:bg-green-600 transition-all ${
                  displayMode.orientation === "horizontal"
                    ? "border-2 border-black"
                    : ""
                }`}
              >
                <ArrowRightIcon className="w-5 h-5 mr-1" />
                Horizontal
              </button>
            </td>
          </tr>

          {/* Display Items */}
          {Object.entries({
            "On/Off": "Toggle the display on or off",
            Chassis:
              "Front display shows internal temperature and humidity, water leakage detection, and coolant level",
            CPU: "Front display shows CPU temperature and utilization.",
            GPU: "Front display shows GPU temperature and utilization.",
            Memory: "Front display shows memory usage.",
            PSU: "Front display shows power consumption, PSU temperature",
          }).map(([key, description]) => {
            const statusKey = key === "On/Off" ? "display" : key.toLowerCase();
            const status = displayMode[statusKey];

            return (
              <tr key={key} className="border-b border-gray-300">
                <td className="py-2 px-4 border border-gray-300 text-center">
                  {key}
                </td>
                <td className="py-2 px-4 border border-gray-300">
                  {description}
                </td>
                <td className="py-3 px-4 border border-gray-300">
                  <div className="flex flex-col items-center justify-center">
                    <button
                      onClick={() => toggleStatus(key)}
                      className={`relative flex items-center w-20 h-8 rounded-full border-2 border-gray-400 transition-colors duration-300 ${
                        status ? "bg-green-500" : "bg-red-500"
                      }`}
                      disabled={key === "PSU"}
                    >
                      <span
                        className={`absolute left-1 transition-transform duration-300 transform ${
                          status ? "translate-x-11" : "translate-x-0"
                        } bg-white rounded-full w-6 h-6`}
                      />
                      <span
                        className={`text-white font-bold transition-all duration-300 ${
                          status ? "ml-2" : "ml-10"
                        }`}
                      >
                        {status ? "On" : "Off"}
                      </span>
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Mobile Cards */}
      <div className="md:hidden space-y-3">
        {/* Orientation */}
        <div className="rounded-xl border p-3 bg-white shadow-sm">
          <div className="text-sm font-semibold text-gray-700 mb-1">
            Orientation
          </div>
          <div className="text-xs text-gray-500 mb-3">
            Determines the display output orientation.
          </div>
          <div className="flex gap-2">
            <button
              onClick={() =>
                setDisplayMode((prev) => ({ ...prev, orientation: "vertical" }))
              }
              className={`flex-1 h-10 rounded-lg text-sm font-medium ${
                displayMode.orientation === "vertical"
                  ? "bg-green-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              Vertical
            </button>
            <button
              onClick={() =>
                setDisplayMode((prev) => ({
                  ...prev,
                  orientation: "horizontal",
                }))
              }
              className={`flex-1 h-10 rounded-lg text-sm font-medium ${
                displayMode.orientation === "horizontal"
                  ? "bg-green-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              Horizontal
            </button>
          </div>
        </div>

        {/* Display Items */}
        {Object.entries({
          "On/Off": "Toggle the display on or off",
          Chassis:
            "Front display shows internal temperature and humidity, water leakage detection, and coolant level",
          CPU: "Front display shows CPU temperature and utilization.",
          GPU: "Front display shows GPU temperature and utilization.",
          Memory: "Front display shows memory usage.",
          PSU: "Front display shows power consumption, PSU temperature",
        }).map(([key, description]) => {
          const statusKey = key === "On/Off" ? "display" : key.toLowerCase();
          const status = displayMode[statusKey];
          const disabled = key === "PSU";

          return (
            <div key={key} className="rounded-xl border p-2 bg-white shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold text-gray-800">
                    {key}
                  </div>
                  <div className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {description}
                  </div>
                </div>
                <button
                  onClick={() => toggleStatus(key)}
                  disabled={disabled}
                  className={`relative w-16 h-9 shrink-0 rounded-full border-2 transition-colors ${
                    disabled ? "opacity-50 cursor-not-allowed" : ""
                  } ${
                    status
                      ? "bg-green-500 border-green-600"
                      : "bg-red-500 border-red-600"
                  }`}
                >
                  <span
                    className={`absolute left-1 top-1 transition-transform ${
                      status ? "translate-x-7" : "translate-x-0"
                    } bg-white rounded-full w-6 h-6`}
                  />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Rotation Time + Apply */}
      <div className="mt-6 flex flex-col md:flex-row md:items-center md:justify-end gap-2">
        <div className="flex items-center gap-2">
          <span className="text-gray-700 font-bold text-sm sm:text-base">
            Mode rotation time (seconds):
          </span>
          <input
            type="number"
            min="1"
            value={displayMode.rotationTime}
            onChange={(e) => {
              const value = Math.floor(Number(e.target.value));
              if (value < 1) {
                setDisplayMode({ ...displayMode, rotationTime: 1 });
              } else {
                setDisplayMode({ ...displayMode, rotationTime: value });
              }
            }}
            className="border p-1 rounded focus:outline-none focus:ring-2 focus:ring-green-500 
        border-gray-600 w-10 md:w-24 md:p-2"
          />
        </div>
        <button
          onClick={handleDisplayMode}
          className="inline-flex items-center justify-center h-10 px-4 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-all"
          disabled={loadingState.applyDisplayConfig}
        >
          {loadingState.applyDisplayConfig ? (
            <LoadingSpinner color={"white"} />
          ) : (
            <>
              <CheckIcon className="w-5 h-5 mr-2" />
              Apply
            </>
          )}
        </button>
      </div>
    </div>
  );
}
