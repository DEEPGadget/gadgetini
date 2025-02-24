"use client";

import React, { useState, useEffect } from "react";
import {
  ArrowUpIcon,
  ArrowRightIcon,
  CheckIcon,
  ArrowTopRightOnSquareIcon,
} from "@heroicons/react/24/solid";

import LoadingSpinner from "../utils/LoadingSpinner";
import { fetchLocalIP } from "../utils/fetchLocalIP";

export default function Settings() {
  const [loadingApply, setLoadingApply] = useState(false);
  const [rotationTime, setRotationTime] = useState(5);
  const [newIP, setNewIP] = useState("");
  const [loadingIP, setLoadingIP] = useState(false);
  const [staticConfig, setStaticConfig] = useState({
    ip: "",
    netmask: "",
    gateway: "",
    dns1: "",
    dns2: "",
  });

  const [localIP, setLocalIP] = useState("localhost");
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [ipMode, setIpMode] = useState("dhcp");
  const [status, setStatus] = useState({
    orientation: "vertical",
    chassis: true,
    cpu: false,
    gpu: false,
    memory: false,
    psu: false,
  });

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch("/api/update-config");
        if (!response.ok) {
          throw new Error("Failed to fetch config");
        }
        const configData = await response.json();
        console.log(configData);
        setStatus({
          orientation: configData.orientation,
          chassis: configData.chassis,
          cpu: configData.cpu,
          gpu: configData.gpu,
          memory: configData.memory,
          psu: configData.psu,
        });
        setRotationTime(configData.rotationTime);
      } catch (error) {
        console.error("Error loading config:", error);
      } finally {
        setLoadingConfig(false);
      }
    };

    fetchConfig();
    fetchLocalIP().then(setLocalIP);
  }, []);

  {
    /*디스플레이 모드 설정 api 점검*/
  }
  const handleApply = async () => {
    setLoadingApply(true);
    const payload = { status, rotationTime };
    try {
      const response = await fetch("/api/update-config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        console.log("Config updated successfully");
      } else {
        console.error("Failed to update config");
      }
    } catch (error) {
      console.error("Error applying config:", error);
    } finally {
      setLoadingApply(false);
    }
  };

  const toggleStatus = (key) => {
    const lowercaseKey = key.toLowerCase();
    setStatus((prevStatus) => ({
      ...prevStatus,
      [lowercaseKey]: !prevStatus[lowercaseKey],
    }));
  };

  const handleIPChange = async () => {
    setLoadingIP(true);
    const payload =
      ipMode === "static"
        ? {
            mode: "static",
            ip: staticConfig.ip,
            netmask: staticConfig.netmask,
            gateway: staticConfig.gateway,
            dns1: staticConfig.dns1,
            dns2: staticConfig.dns2,
          }
        : { mode: "dhcp" };

    try {
      const response = await fetch("/api/setip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        alert(
          `IP updated: ${staticConfig.ip}/${staticConfig.netmask}
          gateway: ${staticConfig.gateway}
          dns1: ${staticConfig.dns1} 
          dns2: ${staticConfig.dns2} `
        );
      } else {
        alert("Failed to update IP");
      }
    } catch (error) {
      alert("Error updating IP");
    } finally {
      setLoadingIP(false);
    }
  };

  return (
    <div className="p-4">
      {/* 그라파나 접속 버튼, IP 설정 */}
      <div className="mb-6">
        <h2 className="text-xl font-bold">System Configuration</h2>
        <div className="flex gap-2 flex-row items-center mt-4">
          <div className="flex items-center">
            <p className="text-base">
              Current IP :<strong> {localIP}</strong>
            </p>
            <a
              href={`http://${localIP}/dashboard`}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 flex items-center px-4 py-2 text-white rounded-lg transition-all 
             bg-gradient-to-br from-orange-600 to-yellow-500 hover:from-orange-700 hover:to-yellow-600 shadow-md hover:shadow-lg"
            >
              Dashboard
              <ArrowTopRightOnSquareIcon className="w-5 h-5 ml-2" />
            </a>
          </div>
        </div>

        <div className="flex items-center gap-4 mt-4">
          <span className="whitespace-nowrap">Set IP :</span>

          {/* DHCP / Static 선택 라디오 버튼 */}
          <div className="flex items-center gap-4">
            <label className="flex items-center space-x-2">
              <input
                type="radio"
                value="dhcp"
                checked={ipMode === "dhcp"}
                onChange={() => setIpMode("dhcp")}
                className="w-4 h-4 text-blue-500"
              />
              <span>DHCP</span>
            </label>

            <label className="flex items-center space-x-2">
              <input
                type="radio"
                value="static"
                checked={ipMode === "static"}
                onChange={() => setIpMode("static")}
                className="w-4 h-4 text-blue-500"
              />
              <span>Static</span>
            </label>
          </div>

          {/* Static 선택 시 IP / Gateway / DNS 입력 필드 표시 */}
          {ipMode === "static" && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="IP Address"
                value={staticConfig.ip}
                onChange={(e) =>
                  setStaticConfig({ ...staticConfig, ip: e.target.value })
                }
                className="border p-2 rounded w-36 text-left"
              />
              <input
                type="text"
                placeholder="Netmask"
                value={staticConfig.netmask}
                onChange={(e) =>
                  setStaticConfig({ ...staticConfig, netmask: e.target.value })
                }
                className="border p-2 rounded w-36 text-left"
              />
              <input
                type="text"
                placeholder="Gateway"
                value={staticConfig.gateway}
                onChange={(e) =>
                  setStaticConfig({ ...staticConfig, gateway: e.target.value })
                }
                className="border p-2 rounded w-36 text-left"
              />
              <input
                type="text"
                placeholder="DNS 1 (Option)"
                value={staticConfig.dns1}
                onChange={(e) =>
                  setStaticConfig({ ...staticConfig, dns1: e.target.value })
                }
                className="border p-2 rounded w-36 text-left"
              />
              <input
                type="text"
                placeholder="DNS 2 (Option)"
                value={staticConfig.dns2}
                onChange={(e) =>
                  setStaticConfig({ ...staticConfig, dns2: e.target.value })
                }
                className="border p-2 rounded w-36 text-left"
              />
            </div>
          )}

          {/* Update 버튼 */}
          <button
            onClick={handleIPChange}
            className="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all"
            disabled={loadingIP}
          >
            {loadingIP ? "Updating..." : "Update"}
            <CheckIcon className="w-5 h-5 ml-2" />
          </button>
        </div>
      </div>

      {/* 컨트롤 테이블 */}
      <h2 className="text-xl font-bold mb-4">Control Info</h2>
      <div className="overflow-x-auto w-full">
        <table className="w-full bg-white border-separate border-spacing-0 table-auto">
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
            {/* 디스플레이 설정화면 재구성 */}
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
                    setStatus((prevStatus) => ({
                      ...prevStatus,
                      orientation: "vertical",
                    }))
                  }
                  className={`flex items-center bg-green-500 text-white p-2 rounded-lg hover:bg-green-600 transition-all ${
                    status.orientation === "vertical"
                      ? "border-2 border-black"
                      : ""
                  }`}
                >
                  <ArrowUpIcon className="w-5 h-5 mr-1" />
                  Vertical
                </button>
                <button
                  onClick={() =>
                    setStatus((prevStatus) => ({
                      ...prevStatus,
                      orientation: "horizontal",
                    }))
                  }
                  className={`flex items-center bg-green-500 text-white p-2 rounded-lg hover:bg-green-600 transition-all ${
                    status.orientation === "horizontal"
                      ? "border-2 border-black"
                      : ""
                  }`}
                >
                  <ArrowRightIcon className="w-5 h-5 mr-1" />
                  Horizontal
                </button>
              </td>
            </tr>

            {Object.entries({
              Chassis:
                "Monitors internal temperature and humidity, water leakage detection, and coolant level",
              CPU: "Monitors CPU temperature.",
              GPU: "Monitors GPU temperature.",
              Memory: "Monitors memory usage.",
              PSU: "Monitors power consumption, PSU temperature",
            }).map(([key, description]) => (
              <tr key={key} className="border-b border-gray-300 ">
                <td className="py-2 px-4 border border-gray-300 text-center">
                  {key}
                </td>
                <td className="py-2 px-4 border border-gray-300">
                  {description}
                </td>
                <td className="py-2 px-4 border border-gray-300">
                  <div className="flex flex-col items-center justify-center ">
                    <button
                      onClick={() => toggleStatus(key)}
                      className={`relative flex items-center w-20 h-8 rounded-full border-2 border-gray-400 transition-colors duration-300 ${
                        status[key.toLowerCase()]
                          ? "bg-green-500"
                          : "bg-red-500"
                      }`}
                      disabled={key !== "Chassis"}
                    >
                      <span
                        className={`absolute left-1 transition-transform duration-300 transform ${
                          status[key.toLowerCase()]
                            ? "translate-x-11"
                            : "translate-x-0"
                        } bg-white rounded-full w-6 h-6`}
                      />
                      <span
                        className={`text-white font-bold transition-all duration-300 ${
                          status[key.toLowerCase()] ? "ml-2" : "ml-10"
                        }`}
                      >
                        {status[key.toLowerCase()] ? "On" : "Off"}
                      </span>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-6 flex justify-end items-center">
          <label
            className="mr-2 text-gray-700 font-bold"
            htmlFor="rotationTime"
          >
            Mode rotation time (seconds):
          </label>
          <input
            type="number"
            placeholder="5"
            min="1"
            value={rotationTime}
            onChange={(e) => {
              const value = Math.floor(Number(e.target.value));
              if (value < 1) {
                setRotationTime(1);
              } else {
                setRotationTime(value);
              }
            }}
            className="border p-2 rounded focus:outline-none focus:ring-2 focus:ring-green-500 
               border-gray-600 w-16"
          />
          <button
            onClick={handleApply}
            className="flex items-center px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-all ml-2"
            disabled={loadingApply}
          >
            {loadingApply ? (
              <LoadingSpinner />
            ) : (
              <>
                <CheckIcon className="w-5 h-5 mr-2" />
                Apply
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
