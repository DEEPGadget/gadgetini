"use client";
import React, { useState } from "react";
import { CogIcon, PowerIcon } from "@heroicons/react/24/solid";
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
  const [rebooting, setRebooting] = useState(false);
  const { t } = useLocale();

  const handleReboot = async () => {
    if (!window.confirm(t("reboot_confirm"))) return;
    try {
      setRebooting(true);
      const res = await fetch("/api/system/reboot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.error || `HTTP ${res.status}`);
      }
      alert(t("reboot_sent"));
    } catch (e) {
      alert(`${t("reboot_failed")}: ${e?.message || e}`);
    } finally {
      setRebooting(false);
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 sm:p-4 bg-gray-200 gap-3 sm:gap-4">
        <h1 className="text-gray-800 font-bold text-lg pl-4">
          Gadgetini{" "}
          <span className="text-gray-500 font-semibold text-sm sm:text-base">v0.3</span>
        </h1>

        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto pl-4">
          <LocaleToggle />
          <button
            onClick={handleReboot}
            disabled={rebooting}
            className={`inline-flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-1 rounded-md text-xs sm:text-sm
              ${rebooting ? "bg-gray-400" : "bg-red-500 hover:bg-red-600"}
              text-white transition disabled:opacity-70 flex-1 sm:flex-none justify-center sm:justify-start`}
            title="Reboot the system"
          >
            <PowerIcon className="w-4 sm:w-5 h-4 sm:h-5 flex-shrink-0" />
            <span className="sm:hidden">{rebooting ? "..." : t("reboot")}</span>
            <span className="hidden sm:inline">{rebooting ? t("rebooting") : t("reboot")}</span>
          </button>
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
