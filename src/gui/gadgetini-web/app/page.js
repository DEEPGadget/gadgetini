"use client";
import React from "react";
import { CogIcon } from "@heroicons/react/24/solid";
import Settings from "./components/settings";

export default function Home() {
  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center justify-between p-4 bg-gray-200">
        <h1 className="text-gray-800 font-bold text-lg">
          Gadgetini{" "}
          <span className="text-gray-500 font-semibold text-base">v0.2</span>
        </h1>
      </header>
      <div className="flex flex-1">
        <aside className="flex-[1] p-3 bg-gray-100">
          <ul>
            <li className="cursor-pointer p-4 bg-gray-300">
              <CogIcon className="inline-block w-5 h-5 mr-2" />
              Settings
            </li>
          </ul>
        </aside>
        <main className="flex-[9] p-2 overflow-y-auto">
          <Settings />
        </main>
      </div>
    </div>
  );
}
