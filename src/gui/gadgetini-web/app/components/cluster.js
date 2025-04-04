"use client";
import React, { useState, useEffect, useRef } from "react";
import { getNodeList } from "../utils/getNodeList";

export default function Cluster() {
  // TODO node add 할때 사용
  const nodeInputInfo = useRef({
    num: 1,
    ip: "",
    alias: "",
  });
  // TODO node table fetch할때 사용용
  const [nodeTable, setNodeTable] = useState([
    { ip: "192.168.1.100", status: false, alias: "worker" },
  ]);

  //TODO node 한개의 status check 하여 상태 return
  const checkNodeStatus = async (node) => {
    let status;
    return {};
  };
  //TODO nodeTable에 ip 를 기반으로 node들의 상태 return
  const checkAllNodeStatus = async (nodeTable) => {
    nodeTable.map((node) => {
      checkNodeStatus(node);
    });
    setNodeTable(nodeTable);
  };

  useEffect(() => {
    getNodeList().then(setNodeTable);
    checkNodeStatus();
  }, []);

  // TODO cluster ADD 버튼
  const handleClusterAdd = async () => {};
  // TODO nodeTable 에서 node 에 어떤 key를 수정할건지 전달 후 response 처리리
  const handleEdit = async (node) => {
    const payload = {
      ip: node.ip,
      key: node.key,
      value: node.value,
    };
    const response = await fetch("/api/nodelist", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  };
  return (
    <div className="p-4 ">
      {nodeTable.map((node, index) => (
        <div key={index}>{node.ip}</div>
      ))}
    </div>
  );
}
