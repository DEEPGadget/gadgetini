export const getSelfIP = async () => {
  try {
    const response = await fetch("/api/ip/self");
    if (!response.ok) {
      throw new Error("Failed to fetch IPv4");
    }
    const data = await response.json();
    return data?.ip ?? data;
  } catch (error) {
    console.error(error);
  }
};
