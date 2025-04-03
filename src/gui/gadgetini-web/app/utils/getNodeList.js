export const getNodeList = async () => {
  try {
    const response = await fetch("/api/nodelist");
    if (!response.ok) {
      throw new Error("Failed to fetch NodeList");
    }
    const nodeList = await response.json();
    return nodeList;
  } catch (error) {}
};
