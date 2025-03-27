export const getSelfIP = async () => {
  try {
    const reponse = await fetch("/api/ip/self");
    if (!reponse.ok) {
      throw new Error("response error from /api/ip/self");
    }
    const ip = await response.json();
    return ip;
  } catch (error) {
    console.error("[getSelfIP]]", error);
  }
};
