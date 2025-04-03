"use client";
import React, { useState, useEffect, useRef } from "react";
import { getNodeList } from "../utils/getNodeList";

export default function Cluster() {
  const [nodeList, setNodeList] = useState([]);
  useEffect(() => {
    getNodeList().then(setNodeList);
  }, []);
  return (
    <div className="p-4 ">
      {nodeList.map((node, index) => (
        <div key={index}>{node.ip}</div>
      ))}
    </div>
  );
}
