"use client";
import React, { useState, useEffect, useRef } from "react";
import { getNodeList } from "../utils/getNodeList";
import DisplayConfigModal from "./DisplayConfigModal";
import {
  ArrowUpIcon,
  ArrowRightIcon,
  CheckIcon,
  ArrowTopRightOnSquareIcon,
} from "@heroicons/react/24/solid";

export default function Cluster() {
  // TODO node add 할때 사용
  const nodeInputInfo = useRef({
    num: 1,
    ip: "",
    alias: "",
  });
  // TODO node table fetch할때 사용용
  const [nodeTable, setNodeTable] = useState([]);
  // Nodes that selected ad node table
  const [selectedNode, setSelectedNode] = useState([]);
  const [loadingState, setLoadingState] = useState({
    loadingHandleClusterAdd: false,
    loadingNodeTable: false,
    loadingNodesStatus: false,
  });
  //TODO node 한개의 status check 하여 상태 return
  const checkNodeStatus = async (node) => {
    let status;
    return { ip: node.ip, alias: node.alias, status: status };
  };
  //TODO nodeTable에 ip 를 기반으로 node들의 상태 return 후 nodeTable에 추가가
  const checkAllNodeStatus = async (nodeTable) => {
    if (nodeTable.length == 0) return;
    nodeTable.map((node) => {
      checkNodeStatus(node);
    });
  };

  useEffect(() => {
    // getNodeList().then((nodes) => {
    //   setNodeTable(nodes);
    // });
  }, []);
  useEffect(() => {
    //checkAllNodeStatus(nodes);
  }, [nodeTable]);

  // TODO cluster ADD 버튼
  const handleClusterAdd = async () => {
    setLoadingState({ ...loadingState, loadingHandleClusterAdd: true });
    const nodes = createIPTable();
    try {
      // PUT DB Api Call
      const response = await fetch("/api/nodelist", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nodes),
      });
      console.log(response);
      if (!response.ok) {
        throw new Error("Node Table DB Input Error");
      }
      setNodeTable((prev) => [...prev, ...nodes]);
    } catch (error) {
      console.error(error);
    } finally {
      setLoadingState({ ...loadingState, loadingHandleClusterAdd: false });
    }
  };

  // Create IP Table by user input and return the table
  const createIPTable = () => {
    const num = parseInt(nodeInputInfo.current.num?.value);
    const startIp = nodeInputInfo.current.ip?.value;
    const aliasBase = nodeInputInfo.current.alias?.value || "";
    const nodes = [];
    if (!num || !startIp) {
      alert("Invalid Input. Please input num of nodes and IP");
      return;
    }

    // IPv4 format check
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(startIp)) {
      alert(
        "Invalid IP format. Please use a valid IPv4 address (e.g., 192.168.1.1)"
      );
      return;
    }
    const ipParts = startIp.split(".");
    if (ipParts.some((part) => parseInt(part) > 255 || parseInt(part) < 0)) {
      alert("Invalid IP format. Each octet must be between 0 and 255.");
      return;
    }

    // Generate IP addresses in ascending order.
    let lastOctet = parseInt(ipParts[3]);
    for (let i = 0; i < num; i++) {
      const ip = `${ipParts[0]}.${ipParts[1]}.${ipParts[2]}.${lastOctet + i}`;
      const alias = aliasBase ? `${aliasBase}${i}` : undefined;
      nodes.push(alias ? { ip, alias } : { ip });
    }
    return nodes;
  };

  // TODO nodeTable 에서 node 에 어떤 key를 수정할건지 전달 후 response 처리리
  const handleEdit = async (node, key) => {
    const payload = {
      ip: node.ip,
      key,
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
      <div className="mb-6">
        <h2 className="text-xl font-bold">Cluster Setup</h2>
        <div className="flex items-center gap-4 mt-4">
          {/* Input when set IP as static mode */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Number of nodes"
              ref={(el) => (nodeInputInfo.current.num = el)}
              className="border p-2 rounded w-40 text-left"
            />
            <input
              type="text"
              placeholder="IP Address"
              ref={(el) => (nodeInputInfo.current.ip = el)}
              className="border p-2 rounded w-40 text-left"
            />
            <input
              type="text"
              placeholder="Alias"
              ref={(el) => (nodeInputInfo.current.alias = el)}
              className="border p-2 rounded w-40 text-left"
            />
          </div>
          <button
            onClick={handleClusterAdd}
            className="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all"
            disabled={loadingState.loadingHandleClusterAdd}
          >
            {loadingState.loadingHandleClusterAdd ? "Updating..." : "Update"}
            <CheckIcon className="w-5 h-5 ml-2" />
          </button>
        </div>
      </div>

      {/* Display mode control table */}
      <h2 className="text-xl font-bold mb-4">Cluster Table</h2>
      <div className="overflow-x-auto w-full">
        <table className="w-full bg-white border-separate border-spacing-0 table-auto">
          <thead>
            <tr className="border-b-2 border-gray-400">
              <th className="py-2 px-4 border border-gray-300 text-center w-full">
                IP Address
              </th>
              <th className="py-2 px-4 border border-gray-300 text-center w-full">
                Alias
              </th>
              <th className="py-2 px-4 border border-gray-300 text-center w-auto">
                Config
              </th>
              <th className="py-2 px-4 border border-gray-300 text-center w-auto">
                Dashboard
              </th>
            </tr>
          </thead>
          <tbody>
            {nodeTable.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-2 px-4 text-center text-gray-500">
                  No nodes available.
                </td>
              </tr>
            ) : (
              nodeTable.map((node) => (
                <tr key={node.ip} className="border-b border-gray-300">
                  <td className="py-2 px-4 border border-gray-300 ">
                    {node.ip}
                  </td>
                  <td className="py-2 px-4 border border-gray-300">
                    {node.alias}
                  </td>
                  <td className="py-2 px-4 border border-gray-300"></td>
                  <td className="py-2 px-4 border border-gray-300"></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
