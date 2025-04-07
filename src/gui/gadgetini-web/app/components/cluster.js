"use client";
import React, { useState, useEffect, useRef } from "react";
import { getNodeList } from "../utils/getNodeList";
import DisplayConfigModal from "./DisplayConfigModal";

export default function Cluster() {
  // TODO node add 할때 사용
  const nodeInputInfo = useRef({
    num: 1,
    ip: "",
    alias: "",
  });
  // TODO node table fetch할때 사용용
  const [nodeTable, setNodeTable] = useState([
    { ip: "192.168.1.100", alias: "worker" },
  ]);
  // Nodes that selected ad node table
  const [selectedNode, setSelectedNode] = useState([]);
  //TODO node 한개의 status check 하여 상태 return
  const checkNodeStatus = async (node) => {
    let status;
    return { ip: node.ip, alias: node.alias, status: status };
  };
  //TODO nodeTable에 ip 를 기반으로 node들의 상태 return 후 nodeTable에 추가가
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
  const handleEditIP = async (node) => {
    const payload = {
      ip: node.ip,
      key: "ip",
      value: node.value,
    };
    const response = await fetch("/api/nodelist", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }; // TODO nodeTable 에서 node 에 어떤 key를 수정할건지 전달 후 response 처리리
  const handleEditAlias = async (node) => {
    const payload = {
      ip: node.ip,
      key: "alias",
      value: node.value,
    };
    const response = await fetch("/api/nodelist", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  };
  // TODO nodetable 선택 에 적용
  const toggleNodeSelection = (node) => {
    setSelectedNode((prev) =>
      prev.includes(node)
        ? prev.filter((item) => item !== node)
        : [...prev, node]
    );
  };
  // TODO nodetable 선택 에 적용
  const toggleSelectAll = () => {
    if (selectedNode.length === nodeTable.length) {
      setSelectedNode({});
    } else {
      setSelectedNode(nodeTable);
    }
  };
  // TODO table에서 제거및 db 삭제
  const handleDeleteNodes = async (selectedNode) => {
    const response = await fetch("/api/nodelist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "delete",
        nodes: selectedNode.map((node) => ({ ip: node.ip })),
      }),
    });
  }; // TODO nodetable에서 일부 노드 display config
  const handleConfigNodesDisplay = async (selectedNode) => {
    const response = await fetch("/api/nodelist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "configDisplay",
        nodes: selectedNode.map((node) => ({ ip: node.ip })),
      }),
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
