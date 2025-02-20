export const fetchLocalIP = async () => {
  try {
    const response = await fetch("/api/localhostip");
    const data = await response.json();
    console.log(data.ipv4);
    return data.ipv4;
  } catch (error) {
    console.error("Failed to fetch local IP:", error);
  }
};

export const setIP = async (newIP) => {
  try {
    const response = await fetch("/api/setip", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ipv4: newIP }),
    });

    const data = await response.json();
    return data.success ? data.ipv4 : null;
  } catch (error) {
    console.error("Failed to set IP:", error);
    return null;
  }
};
