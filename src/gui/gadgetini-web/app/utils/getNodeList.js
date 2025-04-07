export const getNodeList = async () => {
  try {
    const response = await fetch("/api/nodelist");
    if (!response.ok) {
      throw new Error("Failed to fetch NodeList");
    }
    const nodelist = await response.json();
    return nodelist;
  } catch (error) {}
};
