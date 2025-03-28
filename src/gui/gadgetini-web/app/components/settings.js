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
  //Current IP Info
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
    const payload = { ...IPRefs.current };

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
        alert(`Failed to update IP \n ${message}`);
      }
    } catch (error) {
      alert("Error updating IP");
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
        console.error("Failed to update config");
      }
    } catch (error) {
      console.error("Error applying config:", error);
    } finally {
      setLoadingState({ ...loadingState, applyDisplayConfig: false });
    }
  };

  // FE: Toggle display config
  const toggleStatus = (key) => {
    const lowercaseKey = key.toLowerCase();
    setDisplayMode((prev) => ({
      ...prev,
      [lowercaseKey]: !prev[lowercaseKey],
    }));
  };

  return (
    <div className="p-4">
      <div className="mb-6">
        <h2 className="text-xl font-bold">System Configuration</h2>
        {/* Display Cureent IP, Button accessing Grafana Dashboard */}
        <div className="flex gap-2 flex-row items-center mt-4">
          <div className="flex items-center">
            <p className="text-base">
              Current IP :<strong> {currentIP}</strong>
            </p>
            <a
              href={`http://${currentIP}/dashboard`}
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

          {/* Button selecting IP as DHCP or static */}
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

          {/* Input when set IP as static mode */}
          {IPMode === "static" && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="IP Address"
                ref={(el) => (IPRefs.current.ip = el)}
                className="border p-2 rounded w-36 text-left"
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
      </div>

      {/* Display mode control table */}
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
                    setDisplayMode((prevStatus) => ({
                      ...prevStatus,
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
            {Object.entries({
              Chassis:
                "Front display shows internal temperature and humidity, water leakage detection, and coolant level",
              CPU: "Front display shows CPU temperature and utilization.",
              GPU: "Front display shows GPU temperature and utilization.",
              Memory: "Front display shows memory usage.",
              PSU: "Front display shows power consumption, PSU temperature",
            }).map(([key, description]) => {
              const status = displayMode[key.toLowerCase()];
              return (
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
                          status ? "bg-green-500" : "bg-red-500"
                        }`}
                        disabled={key !== "Chassis"}
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
            value={displayMode.rotationTime}
            onChange={(e) => {
              const value = Math.floor(Number(e.target.value));
              if (value < 1) {
                setDisplayMode({ ...displayMode, rotationTime: 1 });
              } else {
                setDisplayMode({ ...displayMode, rotationTime: value });
              }
            }}
            className="border p-2 rounded focus:outline-none focus:ring-2 focus:ring-green-500 
               border-gray-600 w-16"
          />
          <button
            onClick={handleDisplayMode}
            className="flex items-center px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-all ml-2"
            disabled={loadingState.applyDisplayConfig}
          >
            {loadingState.applyDisplayConfig ? (
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
