import {
  Dialog,
  DialogPanel,
  DialogTitle,
  Transition,
  TransitionChild,
} from "@headlessui/react";
import { Fragment } from "react";

export default function DisplayConfigModal({
  isOpen,
  setIsOpen,
  selectedNodes,
}) {
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
                    <ul className="space-y-2">
                      {selectedNodes.map((node) => (
                        <li
                          key={node.ip}
                          className="text-sm border-b border-gray-200 pb-1"
                        >
                          <strong>IP:</strong> {node.ip} <br />
                          <strong>Alias:</strong> {node.alias || "-"}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="mt-6 flex justify-end">
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
