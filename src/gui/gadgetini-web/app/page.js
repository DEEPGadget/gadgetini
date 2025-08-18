"use client";
import React, { useState } from "react";
import { CogIcon } from "@heroicons/react/24/solid";
import Settings from "./components/settings";

export default function Home() {
  const [selectedMenu, setSelectedMenu] = useState("settings");
  const [activeComponent, setActiveComponent] = useState(<Settings />);
  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center justify-between p-4 bg-gray-200">
        <h1 className="text-gray-800 font-bold text-lg">
          Gadgetini{" "}
          <span className="text-gray-500 font-semibold text-base">v0.3</span>
        </h1>
      </header>
      <div className="flex flex-1">
        <aside className=" p-3 bg-gray-100 hidden md:block">
          <ul className="space-y-2">
            <li
              className={`cursor-pointer p-4 rounded ${
                selectedMenu === "settings"
                  ? "bg-gray-300"
                  : "hover:bg-gray-200"
              }`}
              onClick={() => setSelectedMenu("settings")}
            >
              <CogIcon className="inline-block w-5 h-5 mr-2" />
              Settings
            </li>
          </ul>
        </aside>
        <main className="flex-[1] p-2 overflow-y-auto">{activeComponent}</main>
      </div>
    </div>
  );
}
