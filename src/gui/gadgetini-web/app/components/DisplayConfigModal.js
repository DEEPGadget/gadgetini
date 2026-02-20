import {
  Dialog,
  DialogPanel,
  DialogTitle,
  Transition,
  TransitionChild,
} from "@headlessui/react";
import { Fragment, useState } from "react";

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
  const toggleStatus = (key) => {
    setDisplayMode((prev) => ({ ...prev, [key]: !prev[key] }));
  };

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
    } catch (error) {
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
              <DialogPanel className="w-full max-w-lg transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                <DialogTitle className="text-lg font-medium text-gray-900">
                  Display Config
                </DialogTitle>
                <div className="mt-4">
                  {selectedNodes.length === 0 ? (
                    <p className="text-sm text-gray-500">No nodes selected.</p>
                  ) : (
                    <table className="w-full bg-white border-separate border-spacing-0 table-auto">
                      <thead>
                        <tr className="border-b-2 border-gray-400">
                          <th className="py-2 px-4 border border-gray-300 text-center w-auto">
                            Info
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
                              Horizontal
                            </button>
                          </td>
                        </tr>
                        {Object.entries({
                          display: "Turn LCD display on/off entirely.",
                          coolant: "Coolant overview screen (summary view).",
                          coolant_detail: "Coolant detail screen (per-loop inlet/outlet/delta temps).",
                          chassis: "Chassis screen: air temp/humidity, leak detection, coolant level.",
                          cpu: "CPU screen: temperature and utilization.",
                          gpu: "GPU screen: temperature and power.",
                          memory: "Memory screen: available memory.",
                          coolant_daily: "Coolant daily history chart.",
                          gpu_daily: "GPU daily history chart.",
                          cpu_daily: "CPU daily history chart.",
                          psu: "PSU screen: power consumption and temperature.",
                          leak: "Show leak alert overlay when leak is detected.",
                        }).map(([key, description]) => {
                          const status = displayMode[key];
                          const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                          return (
                            <tr key={key} className="border-b border-gray-300">
                              <td className="py-2 px-4 border border-gray-300 text-center">
                                {label}
                              </td>
                              <td className="py-2 px-4 border border-gray-300">
                                <div className="flex flex-col items-center justify-center">
                                  <button
                                    onClick={() => toggleStatus(key)}
                                    className={`relative flex items-center w-20 h-8 rounded-full border-2 border-gray-400 transition-colors duration-300 ${
                                      status ? "bg-green-500" : "bg-red-500"
                                    }`}
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
                        <tr className="border-b border-gray-300">
                          <td className="py-2 px-4 border border-gray-300 text-center">
                            Rotation (sec)
                          </td>
                          <td className="py-2 px-4 border border-gray-300">
                            <div className="flex justify-center">
                              <input
                                type="number"
                                min={1}
                                max={60}
                                value={displayMode.rotationTime}
                                onChange={(e) =>
                                  setDisplayMode((prev) => ({
                                    ...prev,
                                    rotationTime: parseInt(e.target.value) || 5,
                                  }))
                                }
                                className="w-20 border border-gray-300 rounded px-2 py-1 text-center"
                              />
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  )}
                </div>
                <div className="mt-6 flex justify-end">
                  {selectedNodes > 0 && (
                    <button
                      onClick={handleConfigNodesDisplay}
                      className="flex items-center px-4 py-2 mr-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all"
                    >
                      {loading ? "Updating..." : "Update"}
                    </button>
                  )}
                  <button
                    onClick={() => setIsOpen(false)}
                    className="flex items-center px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-700 transition-all"
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
