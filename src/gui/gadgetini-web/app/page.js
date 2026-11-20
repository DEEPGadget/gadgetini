"use client";
import React, { useState } from "react";
import { CogIcon } from "@heroicons/react/24/solid";
import Settings from "./components/settings";
import { LocaleProvider, useLocale } from "./i18n";

function LocaleToggle() {
  const { locale, setLocale } = useLocale();
  const btn = (lang, label) =>
    `px-2 py-1 text-xs font-semibold transition ${
      locale === lang
        ? "bg-gray-700 text-white"
        : "bg-white text-gray-700 hover:bg-gray-100"
    }`;
  return (
    <div className="inline-flex rounded-md overflow-hidden border border-gray-300">
      <button
        onClick={() => setLocale("en")}
        className={btn("en")}
        title="English"
      >
        EN
      </button>
      <button
        onClick={() => setLocale("ko")}
        className={btn("ko")}
        title="Korean"
      >
        KO
      </button>
    </div>
  );
}

function HomeInner() {
  const [selectedMenu, setSelectedMenu] = useState("settings");
  const [activeComponent] = useState(<Settings />);
  const { t } = useLocale();

  return (
    <div className="h-screen flex flex-col">
      <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 sm:p-4 bg-gray-200 gap-3 sm:gap-4">
        <h1 className="text-gray-800 font-bold text-lg pl-4">
          Gadgetini{" "}
          <span className="text-gray-500 font-semibold text-sm sm:text-base">v0.3</span>
        </h1>

        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto pl-4">
          <LocaleToggle />
        </div>
      </header>

      <div className="flex flex-1">
        <aside className="p-3 bg-gray-100 hidden md:block">
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
              {t("settings")}
            </li>
          </ul>
        </aside>
        <main className="flex-[1] p-2 overflow-y-auto">{activeComponent}</main>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <LocaleProvider>
      <HomeInner />
    </LocaleProvider>
  );
}
