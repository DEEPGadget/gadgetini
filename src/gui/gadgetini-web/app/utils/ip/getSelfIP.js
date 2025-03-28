export const getSelfIP = async () => {
  try {
    const response = await fetch("/api/ip/self");
    if (!response.ok) {
      throw new Error("Failed to fetch IPv4");
    }
    const ip = await response.json();
    return ip;
  } catch (error) {
    console.error(error);
  }
};
