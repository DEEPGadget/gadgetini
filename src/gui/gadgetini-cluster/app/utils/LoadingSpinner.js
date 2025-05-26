import React from "react";

export default function LoadingSpinner({ color }) {
  return (
    <div className="flex justify-center items-center">
      <div
        className={`animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-${color}`}
      ></div>
    </div>
  );
}
