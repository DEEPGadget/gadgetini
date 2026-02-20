import {
  Dialog,
  DialogPanel,
  DialogTitle,
  Transition,
  TransitionChild,
} from "@headlessui/react";
import { Fragment, useState } from "react";

function Toggle({ value, onChange }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onChange();
      }}
      className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
        value ? "bg-green-400" : "bg-gray-300"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-transform duration-200 ${
          value ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function SectionHeader({ label, colorClass }) {
  return (
    <div className={`px-4 py-2.5 ${colorClass}`}>
      <span className="text-xs font-bold uppercase tracking-widest text-white/90">
        {label}
      </span>
    </div>
  );
}

function GridCard({ label, stateKey, displayMode, setDisplayMode, activeClass }) {
  const isOn = displayMode[stateKey];
  return (
    <button
      onClick={() =>
        setDisplayMode((p) => ({ ...p, [stateKey]: !p[stateKey] }))
      }
      className={`rounded-xl p-3 flex flex-col gap-2 text-left w-full transition-all duration-200 ${
        isOn ? activeClass : "bg-gray-100 border border-gray-200 text-gray-400"
      }`}
    >
      <span className="text-sm font-semibold leading-tight">{label}</span>
      <span className="text-xs font-bold opacity-75">
        {isOn ? "● ON" : "○ OFF"}
      </span>
    </button>
  );
}

export default function DisplayConfigModal({
  isOpen,
  setIsOpen,
  selectedNodes,
}) {
  const [loading, setLoading] = useState(false);
  const [displayMode, setDisplayMode] = useState({
    orientation: "vertical",
    display: true,
    coolant: false,
    coolant_detail: true,
    chassis: true,
    cpu: true,
    gpu: true,
    memory: true,
    coolant_daily: true,
    gpu_daily: true,
    cpu_daily: true,
    psu: false,
    leak: true,
    rotationTime: 7,
  });

  const handleConfigNodesDisplay = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/nodelist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "configDisplay",
          selectedNodes,
          displayMode,
        }),
      });
      const data = await response.json();
      console.log(data);
      setIsOpen(false);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-50"
        onClose={() => setIsOpen(false)}
      >
        <TransitionChild
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <DialogPanel className="w-full max-w-2xl transform overflow-hidden rounded-2xl bg-gray-100 p-5 text-left align-middle shadow-2xl transition-all">
                <DialogTitle className="text-base font-bold text-gray-900 mb-4 tracking-tight">
                  Display Config
                </DialogTitle>

                {selectedNodes.length === 0 ? (
                  <p className="text-sm text-gray-400">No nodes selected.</p>
                ) : (
                  <div className="space-y-3">
                    {/* ── General ── */}
                    <div className="rounded-2xl overflow-hidden shadow-sm">
                      <SectionHeader label="General" colorClass="bg-slate-700" />
                      <div className="bg-white p-4 space-y-3">
                        {/* Display master */}
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-semibold text-gray-800">Display</p>
                            <p className="text-xs text-gray-400">LCD master on/off</p>
                          </div>
                          <Toggle
                            value={displayMode.display}
                            onChange={() =>
                              setDisplayMode((p) => ({ ...p, display: !p.display }))
                            }
                          />
                        </div>

                        {/* Orientation */}
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold text-gray-800">Orientation</p>
                          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                            {["vertical", "horizontal"].map((o) => (
                              <button
                                key={o}
                                onClick={() =>
                                  setDisplayMode((p) => ({ ...p, orientation: o }))
                                }
                                className={`px-3 py-1 text-xs rounded-md font-bold transition-all ${
                                  displayMode.orientation === o
                                    ? "bg-slate-700 text-white shadow"
                                    : "text-gray-500 hover:text-gray-700"
                                }`}
                              >
                                {o.charAt(0).toUpperCase() + o.slice(1)}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Rotation */}
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-semibold text-gray-800">Rotation</p>
                            <p className="text-xs text-gray-400">Panel switch interval</p>
                          </div>
                          <div className="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-1.5">
                            <input
                              type="number"
                              min={1}
                              max={60}
                              value={displayMode.rotationTime}
                              onChange={(e) =>
                                setDisplayMode((p) => ({
                                  ...p,
                                  rotationTime: Math.max(1, parseInt(e.target.value) || 1),
                                }))
                              }
                              className="w-10 text-center text-sm font-bold focus:outline-none bg-transparent text-gray-800"
                            />
                            <span className="text-xs text-gray-400">sec</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* ── Compute ── */}
                    <div className="rounded-2xl overflow-hidden shadow-sm">
                      <SectionHeader label="Compute" colorClass="bg-blue-600" />
                      <div className="bg-blue-50/60 p-3 grid grid-cols-3 gap-2">
                        {[
                          { label: "CPU", key: "cpu" },
                          { label: "GPU", key: "gpu" },
                          { label: "Memory", key: "memory" },
                        ].map(({ label, key }) => (
                          <GridCard
                            key={key}
                            label={label}
                            stateKey={key}
                            displayMode={displayMode}
                            setDisplayMode={setDisplayMode}
                            activeClass="bg-blue-100 border border-blue-300 text-blue-800"
                          />
                        ))}
                      </div>
                    </div>

                    {/* ── Cooling & Chassis ── */}
                    <div className="rounded-2xl overflow-hidden shadow-sm">
                      <SectionHeader
                        label="Cooling & Chassis"
                        colorClass="bg-teal-600"
                      />
                      <div className="bg-teal-50/60 p-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {[
                          { label: "Chassis", key: "chassis" },
                          { label: "Coolant", key: "coolant" },
                          { label: "Coolant Detail", key: "coolant_detail" },
                          { label: "Leak", key: "leak" },
                        ].map(({ label, key }) => (
                          <GridCard
                            key={key}
                            label={label}
                            stateKey={key}
                            displayMode={displayMode}
                            setDisplayMode={setDisplayMode}
                            activeClass="bg-teal-100 border border-teal-300 text-teal-800"
                          />
                        ))}
                      </div>
                    </div>

                    {/* ── Daily Graphs ── */}
                    <div className="rounded-2xl overflow-hidden shadow-sm">
                      <SectionHeader label="Daily Graphs" colorClass="bg-violet-600" />
                      <div className="bg-violet-50/60 p-3 grid grid-cols-3 gap-2">
                        {[
                          { label: "CPU Daily", key: "cpu_daily" },
                          { label: "GPU Daily", key: "gpu_daily" },
                          { label: "Coolant Daily", key: "coolant_daily" },
                        ].map(({ label, key }) => (
                          <GridCard
                            key={key}
                            label={label}
                            stateKey={key}
                            displayMode={displayMode}
                            setDisplayMode={setDisplayMode}
                            activeClass="bg-violet-100 border border-violet-300 text-violet-800"
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div className="mt-5 flex justify-end gap-2">
                  {selectedNodes.length > 0 && (
                    <button
                      onClick={handleConfigNodesDisplay}
                      disabled={loading}
                      className="px-4 py-2 bg-slate-800 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 transition-all disabled:opacity-50"
                    >
                      {loading ? "Updating..." : "Update"}
                    </button>
                  )}
                  <button
                    onClick={() => setIsOpen(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 text-sm font-semibold rounded-xl hover:bg-gray-300 transition-all"
                  >
                    Close
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
