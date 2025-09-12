"use client";
import React, { useState } from "react";
import { ServerStackIcon } from "@heroicons/react/24/solid";
import Cluster from "./components/cluster";

export default function Home() {
  const [selectedMenu, setSelectedMenu] = useState("cluster");
  const [activeComponent, setActiveComponent] = useState(<Cluster />);
  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center justify-between p-4 bg-gray-200">
        <h1 className="text-gray-800 font-bold text-lg">
          Gadgetini{" "}
          <span className="text-gray-500 font-semibold text-base">v0.3</span>
        </h1>
      </header>
      <div className="flex flex-1">
        <aside className=" p-3 bg-gray-100">
          <ul className="space-y-2">
            <li
              className={`cursor-pointer p-4 rounded ${
                selectedMenu === "cluster" ? "bg-gray-300" : "hover:bg-gray-200"
              }`}
              onClick={() => setSelectedMenu("cluster")}
            >
              <ServerStackIcon className="inline-block w-5 h-5 mr-2" />
              Cluster
            </li>
          </ul>
        </aside>
        <main className="flex-[1] p-2 overflow-y-auto">{activeComponent}</main>
      </div>
    </div>
  );
}
