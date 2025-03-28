export const getSelfIP = async () => {
  try {
    const response = await fetch("/api/ip/self");
    if (!response.ok) {
      throw new Error("response error from /api/ip/self");
    }
    const ip = await response.json();
    return ip;
  } catch (error) {
    console.error("[getSelfIP]]", error);
  }
};
