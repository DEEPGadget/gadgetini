"use client";

// Core-service health for the System panel, under Current IP.
//
// Read-only: /api/services/health never controls a unit, so a failing cooling service
// can be diagnosed here but not restarted from the browser.
//
// Three levels, because no service in this stack emits a ready-made "summary + detail"
// error (only the six log.exception sites have a traceback at all):
//   1. one headline row — "All services OK (8/8)" — click to expand the list
//   2. one row per service; unhealthy rows get a warning button
//   3. the synthesised one-line summary, with "show detail" pulling the raw journal tail
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDownIcon, ExclamationTriangleIcon } from "@heroicons/react/24/solid";
import { useLocale } from "../i18n";

// systemctl/journalctl fork a process per poll, so this is slower than the 5 s PCB
// status poll and the 500 ms PWM poll elsewhere in the panel.
const POLL_MS = 15000;

// "degraded" = systemd says active but the service is not doing its job
// (e.g. collector running with the PCB unreachable); the API fills in why.
const DOT_CLASS = {
  ok: "bg-green-400",
  pending: "bg-amber-400",
  degraded: "bg-amber-400",
  error: "bg-red-400",
  unknown: "bg-gray-300",
};

const STATE_TEXT_CLASS = {
  pending: "text-amber-600",
  degraded: "text-amber-600",
  error: "text-red-600",
  unknown: "text-gray-500",
};

function fmt(template, values) {
  return Object.entries(values).reduce(
    (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
    String(template),
  );
}

export default function ServiceHealth() {
  const { t } = useLocale();
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [open, setOpen] = useState(false);
  const [openRow, setOpenRow] = useState(null);
  const [details, setDetails] = useState({});
  // Once the user has opened or closed the list by hand, stop auto-expanding it on them.
  const userToggled = useRef(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch("/api/services/health");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!alive) return;
        setData(json);
        setLoadError(false);
      } catch {
        if (alive) setLoadError(true);
      }
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Expand the list by itself the first time something is wrong.
  useEffect(() => {
    if (!userToggled.current && data?.unhealthy > 0) setOpen(true);
  }, [data?.unhealthy]);

  const toggleList = () => {
    userToggled.current = true;
    setOpen((v) => !v);
  };

  // Mirrored in a ref so the fetch/toggle decision can be made before the state update
  // lands — a setState updater runs during the next render, too late to branch on here.
  const detailsRef = useRef({});
  const putDetail = useCallback((key, value) => {
    detailsRef.current = { ...detailsRef.current, [key]: value };
    setDetails(detailsRef.current);
  }, []);

  const loadDetail = useCallback(
    async (key) => {
      const current = detailsRef.current[key];
      if (current?.shown) {
        putDetail(key, { ...current, shown: false });
        return;
      }
      if (current?.lines) {
        putDetail(key, { ...current, shown: true });
        return;
      }
      putDetail(key, { loading: true, shown: true });
      try {
        const res = await fetch(
          `/api/services/health?detail=${encodeURIComponent(key)}`,
        );
        const json = await res.json();
        putDetail(key, { loading: false, shown: true, lines: json?.lines || [] });
      } catch {
        putDetail(key, { loading: false, shown: true, lines: [] });
      }
    },
    [putDetail],
  );

  let headlineStatus = "unknown";
  let headline = t("services_checking");
  if (loadError && !data) {
    headlineStatus = "pending";
    headline = t("services_unavailable");
  } else if (data) {
    const bad = data.unhealthy ?? 0;
    headlineStatus = bad > 0 ? "error" : "ok";
    headline = fmt(bad > 0 ? t("services_attention") : t("services_ok"), {
      ok: data.ok_count,
      bad,
      total: data.total,
    });
  }

  const services = data?.services || [];

  return (
    <div>
      <button
        type="button"
        onClick={toggleList}
        aria-expanded={open}
        disabled={!services.length}
        className="flex items-center gap-1.5 w-full text-left disabled:cursor-default"
      >
        <span
          className={`w-2 h-2 rounded-full flex-shrink-0 ${DOT_CLASS[headlineStatus]}`}
        />
        <span className="text-xs sm:text-sm text-gray-600 flex-1 min-w-0 truncate">
          {headline}
        </span>
        {services.length > 0 && (
          <ChevronDownIcon
            className={`w-3.5 h-3.5 text-gray-400 flex-shrink-0 transition-transform ${
              open ? "rotate-180" : ""
            }`}
          />
        )}
      </button>

      {open && services.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {services.map((svc) => {
            const detail = details[svc.key];
            const expanded = openRow === svc.key;
            return (
              <li key={svc.key}>
                <div className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${DOT_CLASS[svc.status]}`}
                  />
                  <span className="text-xs text-gray-700 flex-1 min-w-0 truncate">
                    {t(`svc_${svc.key}`)}
                  </span>
                  {svc.status !== "ok" && (
                    <>
                      <span
                        className={`text-[11px] font-mono flex-shrink-0 ${
                          STATE_TEXT_CLASS[svc.status] || "text-gray-500"
                        }`}
                      >
                        {svc.state}
                      </span>
                      <button
                        type="button"
                        onClick={() => setOpenRow(expanded ? null : svc.key)}
                        aria-expanded={expanded}
                        title={t("service_show_message")}
                        className="flex-shrink-0 text-amber-500 hover:text-amber-600"
                      >
                        <ExclamationTriangleIcon className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>

                {expanded && (
                  <div className="mt-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 space-y-1">
                    <p className="font-mono text-[11px] text-amber-800 break-all">
                      {svc.unit}
                    </p>
                    {svc.summary?.length ? (
                      svc.summary.map((line, i) => (
                        <p key={i} className="break-words">
                          {line}
                        </p>
                      ))
                    ) : (
                      <p>{t("service_no_message")}</p>
                    )}
                    <button
                      type="button"
                      onClick={() => loadDetail(svc.key)}
                      className="text-[11px] font-bold text-amber-800 underline underline-offset-2"
                    >
                      {detail?.shown
                        ? t("service_detail_hide")
                        : t("service_detail_show")}
                    </button>
                    {detail?.shown && (
                      <div>
                        {detail.loading ? (
                          <p className="text-[11px] text-amber-800">{t("loading")}</p>
                        ) : detail.lines?.length ? (
                          <pre className="max-h-48 overflow-auto bg-gray-50 border border-gray-200 rounded p-2 text-[10px] leading-snug font-mono text-gray-700 whitespace-pre-wrap break-all">
                            {detail.lines.join("\n")}
                          </pre>
                        ) : (
                          <p className="text-[11px] text-amber-800">
                            {t("service_detail_empty")}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
