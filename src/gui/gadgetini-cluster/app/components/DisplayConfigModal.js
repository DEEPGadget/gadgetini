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
      onClick={onChange}
      className={`relative flex-shrink-0 w-12 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
        value ? "bg-green-500" : "bg-gray-300"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
          value ? "translate-x-6" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function ToggleCard({ label, desc, stateKey, displayMode, setDisplayMode }) {
  return (
    <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-gray-700 truncate">{label}</p>
        {desc && <p className="text-xs text-gray-400 truncate">{desc}</p>}
      </div>
      <Toggle
        value={displayMode[stateKey]}
        onChange={() =>
          setDisplayMode((prev) => ({
            ...prev,
            [stateKey]: !prev[stateKey],
          }))
        }
      />
    </div>
  );
}

function SectionCard({ title, colorClass, children }) {
  return (
    <div className={`bg-white rounded-xl border p-4 shadow-sm ${colorClass}`}>
      <h3 className={`text-xs font-bold uppercase tracking-wider mb-3 ${colorClass}`}>
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function DisplayConfigModal({
  isOpen,
  setIsOpen,
  selectedNodes,
}) {
  const [loading, setLoading] = useState(false);
  const [displayMode, setDisplayMode] = useState({
    orientation: "horizontal",
    display: true,
    chassis: true,
    cpu: true,
    gpu: true,
    memory: true,
    psu: false,
    coolant: false,
    coolantDetail: true,
    coolantDaily: true,
    gpuDaily: true,
    cpuDaily: true,
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
          <div className="fixed inset-0 bg-black/40" />
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
              <DialogPanel className="w-full max-w-2xl transform overflow-hidden rounded-2xl bg-gray-100 p-5 text-left align-middle shadow-xl transition-all">
                <DialogTitle className="text-lg font-semibold text-gray-900 mb-4">
                  Display Config
                </DialogTitle>

                {selectedNodes.length === 0 ? (
                  <p className="text-sm text-gray-500">No nodes selected.</p>
                ) : (
                  <div className="space-y-3">
                    {/* General */}
                    <div className="bg-white rounded-xl border border-blue-100 p-4 shadow-sm">
                      <h3 className="text-xs font-bold uppercase tracking-wider mb-3 text-blue-600">
                        General
                      </h3>
                      <div className="space-y-3">
                        {/* Master Switch */}
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-800">Display</p>
                            <p className="text-xs text-gray-400">Master on/off switch</p>
                          </div>
                          <Toggle
                            value={displayMode.display}
                            onChange={() =>
                              setDisplayMode((p) => ({ ...p, display: !p.display }))
                            }
                          />
                        </div>

                        {/* Orientation */}
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <p className="text-sm font-medium text-gray-800">Orientation</p>
                          <div className="flex gap-2">
                            {["vertical", "horizontal"].map((o) => (
                              <button
                                key={o}
                                onClick={() =>
                                  setDisplayMode((p) => ({ ...p, orientation: o }))
                                }
                                className={`px-3 py-1 text-sm rounded-lg font-medium transition-all ${
                                  displayMode.orientation === o
                                    ? "bg-blue-500 text-white shadow"
                                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                }`}
                              >
                                {o.charAt(0).toUpperCase() + o.slice(1)}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Rotation */}
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div>
                            <p className="text-sm font-medium text-gray-800">Rotation</p>
                            <p className="text-xs text-gray-400">Panel switch interval</p>
                          </div>
                          <div className="flex items-center gap-2">
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
                              className="w-16 text-center border border-gray-300 rounded-lg py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                            />
                            <span className="text-sm text-gray-500">sec</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Real-time Panels */}
                    <div className="bg-white rounded-xl border border-green-100 p-4 shadow-sm">
                      <h3 className="text-xs font-bold uppercase tracking-wider mb-3 text-green-600">
                        Real-time Panels
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {[
                          { label: "Chassis", key: "chassis", desc: "Temp, humidity, coolant" },
                          { label: "CPU", key: "cpu", desc: "Temperature & utilization" },
                          { label: "GPU", key: "gpu", desc: "Temperature & utilization" },
                          { label: "Memory", key: "memory", desc: "RAM usage" },
                          { label: "PSU", key: "psu", desc: "Power & temperature" },
                          { label: "Coolant", key: "coolant", desc: "Coolant level" },
                          { label: "Coolant Detail", key: "coolantDetail", desc: "Detailed coolant info" },
                          { label: "Leak", key: "leak", desc: "Water leak detection" },
                        ].map(({ label, key, desc }) => (
                          <ToggleCard
                            key={key}
                            label={label}
                            desc={desc}
                            stateKey={key}
                            displayMode={displayMode}
                            setDisplayMode={setDisplayMode}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Daily Graphs */}
                    <div className="bg-white rounded-xl border border-purple-100 p-4 shadow-sm">
                      <h3 className="text-xs font-bold uppercase tracking-wider mb-3 text-purple-600">
                        Daily Graphs
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        {[
                          { label: "CPU Daily", key: "cpuDaily" },
                          { label: "GPU Daily", key: "gpuDaily" },
                          { label: "Coolant Daily", key: "coolantDaily" },
                        ].map(({ label, key }) => (
                          <ToggleCard
                            key={key}
                            label={label}
                            stateKey={key}
                            displayMode={displayMode}
                            setDisplayMode={setDisplayMode}
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
                      className="px-4 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600 transition-all disabled:opacity-50"
                    >
                      {loading ? "Updating..." : "Update"}
                    </button>
                  )}
                  <button
                    onClick={() => setIsOpen(false)}
                    className="px-4 py-2 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-700 transition-all"
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
