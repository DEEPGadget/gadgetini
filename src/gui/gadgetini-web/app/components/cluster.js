"use client";
import React, { useState, useEffect, useRef } from "react";
import { getNodeList } from "../utils/getNodeList";
import DisplayConfigModal from "./DisplayConfigModal";
import {
  CheckIcon,
  ArrowTopRightOnSquareIcon,
  TrashIcon,
  Cog6ToothIcon,
  CheckCircleIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/solid";
import { getSelfIP } from "../utils/ip/getSelfIP";
import LoadingSpinner from "../utils/LoadingSpinner";

export default function Cluster() {
  // Input refs
  const nodeInputInfo = useRef({
    num: 1,
    ip: "",
    alias: "",
  });
  const editNodeInputInfo = useRef({
    ip: "",
    alias: "",
  });
  // TODO node table fetch할때 사용용
  const [nodeTable, setNodeTable] = useState([]);
  // Nodes that selected ad node table
  const [selectedNode, setSelectedNode] = useState([]);
  const [loadingState, setLoadingState] = useState({
    loadingHandleClusterAdd: false,
    loaddingDeleteNodes: false,
    loadingNodeTable: false,
    loadingNodesStatus: false,
    loadingEditStatus: false,
    loadingTableRefreshStatus: false,
  });
  const [currentIP, setCurrentIP] = useState("localhost");
  const [reloadTrigger, setReloadTrigger] = useState(0);

  const [isModalOpen, setIsModalOpen] = useState(false);

  // Check node connection status and return
  const checkNodeStatus = async (node) => {
    try {
      const response = await fetch("/api/node", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(node),
      });
      const data = await response.json();
      return { ...node, status: data.status };
    } catch (error) {
      return { ...node, status: "unknown" };
    }
  };

  useEffect(() => {
    const fetchAndUpdateTable = async () => {
      setLoadingState((prev) => ({
        ...prev,
        loadingTableRefreshStatus: true,
      }));

      try {
        const nodes = await getNodeList();
        const statusCheckedNodeTable = await Promise.all(
          nodes.map(checkNodeStatus)
        );
        setNodeTable(
          statusCheckedNodeTable.map((node) => ({
            ...node,
            editActive: { ip: false, alias: false },
          }))
        );
      } catch (err) {
        console.error("Error loading table:", err);
      } finally {
        setLoadingState((prev) => ({
          ...prev,
          loadingTableRefreshStatus: false,
        }));
      }
    };
    fetchAndUpdateTable();
  }, [reloadTrigger]);

  useEffect(() => {
    getSelfIP().then(setCurrentIP);
  }, []);

  // Add nodes to cluster table
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
      if (!response.ok) {
        console.log(response.json());
        throw new Error("Node Table DB Input Error");
      }
      setReloadTrigger((prev) => prev + 1);
    } catch (error) {
      alert(error);
    } finally {
      setLoadingState({ ...loadingState, loadingHandleClusterAdd: false });
    }
  };

  // Create IP Table by user input and return the table
  const createIPTable = () => {
    const num = parseInt(nodeInputInfo.current.num?.value);
    const startIp = nodeInputInfo.current.ip?.value;
    const aliasInput = nodeInputInfo.current.alias?.value || "";
    const nodes = [];
    if (!num || !startIp) {
      alert("Invalid Input. Please input num of nodes and IP");
      return;
    }

    // Get IPv4 format
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
    // Get Alias format
    const aliasMatch = aliasInput.match(/^(.*?)(\d+)?$/);
    const aliasBase = aliasMatch?.[1] || "";
    const startAliasIndex = aliasMatch?.[2] ? parseInt(aliasMatch[2]) : 0;
    const maxIndex = startAliasIndex + num - 1;
    const paddingLength = Math.max(
      aliasMatch?.[2]?.length || 0,
      String(maxIndex).length
    );

    // Generate IP addresses in ascending order.
    let lastOctet = parseInt(ipParts[3]);
    for (let i = 0; i < num; i++) {
      const ip = `${ipParts[0]}.${ipParts[1]}.${ipParts[2]}.${lastOctet + i}`;
      const alias = aliasInput
        ? `${aliasBase}${String(startAliasIndex + i).padStart(
            paddingLength,
            "0"
          )}`
        : undefined;
      nodes.push(alias ? { ip, alias } : { ip });
    }
    return nodes;
  };

  // Edit IP address or Alias
  const handleEdit = async (node, key) => {
    setNodeTable((prevNodes) =>
      prevNodes.map((item) =>
        item.ip === node.ip
          ? {
              ...item,
              editActive: { ...item.editActive, [key]: !item.editActive[key] },
            }
          : item
      )
    );
  };

  // Apply edited content at Cluster table
  const handleApply = async (node, key) => {
    setLoadingState({ ...loadingState, loadingEditStatus: true });
    const value =
      key === "ip"
        ? editNodeInputInfo.current.ip?.value
        : editNodeInputInfo.current.alias?.value;
    if (!value) {
      alert(`Please enter a value for ${key}.`);
      return;
    }
    const payload = {
      ip: node.ip,
      key,
      value,
    };
    try {
      const response = await fetch("/api/nodelist", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setReloadTrigger((prev) => prev + 1);
      }
    } catch (error) {
      console.error("Error updating node:", error);
      alert("Error occurred while updating node.");
    } finally {
      setLoadingState({ ...loadingState, loadingEditStatus: false });
    }
  };

  // Toggle one node at Cluster Table
  const toggleNodeSelection = (node) => {
    setSelectedNode((prev) =>
      prev.includes(node)
        ? prev.filter((item) => item !== node)
        : [...prev, node]
    );
  };
  // Toggle all nodes at Cluster Table
  const toggleSelectAll = () => {
    if (selectedNode.length === nodeTable.length) {
      setSelectedNode([]);
    } else {
      setSelectedNode([...nodeTable]);
    }
  };

  // Delete Nodes at Cluster Table
  const handleDeleteNodes = async (selectedNode) => {
    setLoadingState({ ...setLoadingState, loaddingDeleteNodes: true });
    if (selectedNode.length == 0) return;
    if (!window.confirm("Are you sure you want to Delete the Nodes?")) {
      return;
    }
    try {
      const response = await fetch("/api/nodelist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "delete",
          nodes: selectedNode,
        }),
      });
      if (response.ok) {
        setNodeTable((prevNodes) =>
          prevNodes.filter((node) => !selectedNode.includes(node))
        );
        setSelectedNode([]);
      } else {
        console.error("Failed to delete nodes:", await response.json());
        alert("Failed to delete nodes. Please check the console for details.");
      }
    } catch (error) {
      console.error("Error deleting nodes:", error);
      alert("Error occurred while deleting nodes");
    } finally {
      setLoadingState({ ...setLoadingState, loaddingDeleteNodes: false });
    }
  };
  // TODO nodetable에서 일부 노드 display config

  return (
    <div className="p-4 ">
      <div className="mb-6">
        <h2 className="text-xl font-bold">Cluster Setup</h2>
        <div className="flex items-center gap-4 mt-4">
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

      <div className="mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          Cluster Table
          {loadingState.loadingTableRefreshStatus && (
            <LoadingSpinner color={"black"} />
          )}
        </h2>
      </div>
      <div className="flex flex-col">
        <div className="flex justify-end mb-2">
          <button
            onClick={() => handleDeleteNodes(selectedNode)}
            className="flex items-center px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-all mr-2"
          >
            Delete
            <TrashIcon className="w-5 h-5 ml-2" />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-all"
          >
            Display Config
            <Cog6ToothIcon className="w-5 h-5 ml-2" />
          </button>
          <a
            href={`http://${currentIP}/dashboard`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 flex items-center px-4 py-2 text-white rounded-lg transition-all 
                       bg-gradient-to-br from-orange-600 to-yellow-500 hover:from-orange-700 hover:to-yellow-600 shadow-md hover:shadow-lg"
          >
            Cluster Dashboard
            <ArrowTopRightOnSquareIcon className="w-5 h-5 ml-2" />
          </a>
        </div>
      </div>
      <div className="overflow-x-auto w-full">
        <table className="w-full bg-white border-separate border-spacing-0 table-fixed">
          <thead>
            <tr className="border-b-2 border-gray-400">
              <th className="py-2 px-4 border border-gray-300 text-center w-12">
                <input
                  type="checkbox"
                  onChange={toggleSelectAll}
                  checked={
                    nodeTable.length > 0 &&
                    selectedNode.length === nodeTable.length
                  }
                />
              </th>
              <th className="py-2 px-4 border border-gray-300 text-center flex-[4_1_0%]">
                IP Address
              </th>
              <th className="py-2 px-4 border border-gray-300 text-center flex-[3_1_0%]">
                Alias
              </th>
              <th className="py-2 px-4 border border-gray-300 text-center w-36">
                Settings
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
                  <td className="py-2 px-4 border border-gray-300 text-center ">
                    <input
                      type="checkbox"
                      checked={selectedNode.includes(node)}
                      onChange={() => toggleNodeSelection(node)}
                    />
                  </td>
                  <td className="py-2 px-4 border border-gray-300 ">
                    <div className="flex items-center gap-2">
                      {node.editActive.ip ? (
                        <>
                          <input
                            type="text"
                            ref={(el) => (editNodeInputInfo.current.ip = el)}
                            className="border border-gray-500 rounded-md p-2 w-40 text-left"
                          />
                          <button
                            onClick={() => handleApply(node, "ip")}
                            className="flex items-center ml-2 px-4 py-1 bg-white text-black border border-gray-500 hover:text-white rounded-lg hover:bg-gray-500 transition-all"
                          >
                            {loadingState.loadingEditStatus ? (
                              <LoadingSpinner color={"white"} />
                            ) : (
                              <>Apply</>
                            )}
                          </button>
                        </>
                      ) : (
                        <>
                          <span>{node.ip}</span>
                          {node.status === "active" ? (
                            <CheckCircleIcon className="w-5 h-5 text-green-500" />
                          ) : node.status === "inactive" ? (
                            <XCircleIcon className="w-5 h-5 text-red-500" />
                          ) : (
                            <QuestionMarkCircleIcon className="w-5 h-5 text-gray-700" />
                          )}
                          <button
                            onClick={() => handleEdit(node, "ip")}
                            className="flex items-center ml-3 px-4 py-1 bg-white text-black border border-gray-500 hover:text-white rounded-lg hover:bg-gray-500 transition-all"
                          >
                            Edit
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="py-2 px-4 border border-gray-300 ">
                    <div className="flex items-center gap-2">
                      {node.editActive.alias ? (
                        <>
                          <input
                            type="text"
                            ref={(el) => (editNodeInputInfo.current.alias = el)}
                            className="border border-gray-500 rounded-md p-2 w-40 text-left"
                          />
                          <button
                            onClick={() => handleApply(node, "alias")}
                            className="flex items-center ml-2 px-4 py-1 bg-white text-black border border-gray-500 hover:text-white rounded-lg hover:bg-gray-500 transition-all"
                          >
                            {loadingState.loadingEditStatus ? (
                              <LoadingSpinner color={"white"} />
                            ) : (
                              <>Apply</>
                            )}
                          </button>
                        </>
                      ) : (
                        <>
                          <span>{node.alias}</span>
                          <button
                            onClick={() => handleEdit(node, "alias")}
                            className="flex items-center ml-2 px-4 py-1 bg-white text-black border border-gray-500 hover:text-white rounded-lg hover:bg-gray-500 transition-all"
                          >
                            Edit
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="py-2 px-4 border border-gray-300 ">
                    <a
                      href={`http://${node.ip}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center px-4 py-2 bg-black text-white rounded-lg hover:opacity-80 transition-opacity "
                    >
                      Setting
                      <Cog6ToothIcon className="w-5 h-5 ml-2" />
                    </a>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <DisplayConfigModal
        isOpen={isModalOpen}
        setIsOpen={setIsModalOpen}
        selectedNodes={selectedNode}
      />
    </div>
  );
}
