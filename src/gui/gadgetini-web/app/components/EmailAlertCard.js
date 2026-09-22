"use client";
// Grafana email alert (SMTP) settings → /api/grafana/smtp → /etc/grafana/grafana.ini [smtp].
// The stored password is never sent back to the browser; leaving the field empty keeps it
// (allowed only while host/user are unchanged — the API enforces this).
import React, { useEffect, useState } from "react";
import { CheckIcon, TrashIcon } from "@heroicons/react/24/solid";
import LoadingSpinner from "../utils/LoadingSpinner";
import { useLocale } from "../i18n";

const STARTTLS_POLICIES = ["MandatoryStartTLS", "OpportunisticStartTLS", "NoStartTLS"];

const inputClass =
  "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:bg-gray-50 disabled:text-gray-500";

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="block text-xs sm:text-sm text-gray-700 font-bold mb-1">{label}</span>
      {children}
      {hint && <span className="block text-xs text-gray-500 mt-0.5">{hint}</span>}
    </label>
  );
}

function SectionHeader({ label, colorClass }) {
  return (
    <div className={`px-3 sm:px-4 py-2.5 ${colorClass}`}>
      <span className="text-base font-bold uppercase tracking-wider text-white/90">
        {label}
      </span>
    </div>
  );
}

export default function EmailAlertCard() {
  const { t } = useLocale();
  const [form, setForm] = useState({
    enabled: false,
    host: "",
    user: "",
    password: "",
    from_address: "",
    from_name: "",
    startTLS_policy: "MandatoryStartTLS",
  });
  const [passwordSet, setPasswordSet] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = () =>
    fetch("/api/grafana/smtp")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const { passwordSet: ps, ...rest } = d;
        setForm({ ...rest, password: "" });
        setPasswordSet(ps);
      })
      .catch(() => {})
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const set = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }));

  const handleSave = async () => {
    if (!window.confirm(t("smtp_save_confirm"))) return;
    setSaving(true);
    try {
      const r = await fetch("/api/grafana/smtp", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        alert(`${t("save_failed")}: ${d.error || r.status}`);
        return;
      }
      alert(t("smtp_saved"));
      await load();
    } catch (err) {
      alert(`${t("save_failed")}: ${err?.message || err}`);
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm(t("smtp_clear_confirm"))) return;
    setSaving(true);
    try {
      const r = await fetch("/api/grafana/smtp", { method: "DELETE" });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        alert(`${t("save_failed")}: ${d.error || r.status}`);
        return;
      }
      await load();
    } catch (err) {
      alert(`${t("save_failed")}: ${err?.message || err}`);
    } finally {
      setSaving(false);
    }
  };

  const disabled = !form.enabled || saving;

  return (
    <div className="rounded-2xl overflow-hidden shadow-sm">
      <SectionHeader label={t("section_email_alert")} colorClass="bg-indigo-700" />
      <div className="bg-white p-3 sm:p-4 space-y-3">
        {loading ? (
          <p className="text-xs text-gray-600">{t("loading")}</p>
        ) : (
          <>
            <p className="text-xs text-gray-600">{t("smtp_desc")}</p>

            <div className="flex items-center justify-between bg-gray-50 rounded-xl p-3">
              <p className="text-sm font-bold text-gray-800">{t("smtp_enabled")}</p>
              <button
                onClick={() => setForm((p) => ({ ...p, enabled: !p.enabled }))}
                className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
                  form.enabled ? "bg-green-400" : "bg-gray-300"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-transform duration-200 ${
                    form.enabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <Field label="host" hint={t("smtp_host_hint")}>
              <input type="text" className={inputClass} disabled={disabled}
                placeholder="smtp.example.com:587" value={form.host} onChange={set("host")} />
            </Field>
            <Field label="user" hint={t("smtp_user_hint")}>
              <input type="text" className={inputClass} disabled={disabled} autoComplete="off"
                placeholder="noreply@example.com" value={form.user} onChange={set("user")} />
            </Field>
            <Field label="password" hint={passwordSet ? t("smtp_password_keep") : t("smtp_password_hint")}>
              <input type="password" className={inputClass} disabled={disabled} autoComplete="new-password"
                placeholder={passwordSet ? "••••••••" : ""} value={form.password} onChange={set("password")} />
            </Field>
            <Field label="from_address" hint={t("smtp_from_address_hint")}>
              <input type="email" className={inputClass} disabled={disabled}
                placeholder="noreply@example.com" value={form.from_address} onChange={set("from_address")} />
            </Field>
            <Field label="from_name" hint={t("smtp_from_name_hint")}>
              <input type="text" className={inputClass} disabled={disabled}
                placeholder="Example Monitoring" value={form.from_name} onChange={set("from_name")} />
            </Field>
            <Field label="startTLS_policy" hint={t("smtp_starttls_hint")}>
              <select className={inputClass} disabled={disabled}
                value={form.startTLS_policy} onChange={set("startTLS_policy")}>
                {STARTTLS_POLICIES.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </Field>

            <div className="flex gap-2">
              <button
                onClick={handleClear}
                disabled={saving || !passwordSet}
                className="flex items-center justify-center px-3 py-2 bg-white text-gray-700 text-sm font-bold rounded-xl border border-gray-300 hover:bg-gray-50 transition-all disabled:opacity-50"
              >
                <TrashIcon className="w-4 h-4 mr-1" />
                {t("smtp_clear")}
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 flex items-center justify-center px-3 py-2 bg-indigo-600 text-white text-sm font-bold rounded-xl hover:bg-indigo-700 transition-all disabled:opacity-50"
              >
                {saving ? (
                  <LoadingSpinner color={"white"} />
                ) : (
                  <>
                    {t("save")}
                    <CheckIcon className="w-4 h-4 ml-2" />
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
