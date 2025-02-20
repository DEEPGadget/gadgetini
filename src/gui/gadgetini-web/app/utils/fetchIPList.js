// /utils/fetchIPList.js

export const fetchIPList = async () => {
  try {
    const response = await fetch("/api/ip");
    if (!response.ok) throw new Error("Network response was not ok.");
    const data = await response.json();
    return data;
    console.log(data);
  } catch (error) {
    console.error("Failed to fetch iplist:", error);
    return [];
  }
};
