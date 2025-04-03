export const getDisplayConfig = async () => {
  try {
    const response = await fetch("/api/display-config");
    if (!response.ok) {
      throw new Error("Failed to fetch display config");
    }
    const configData = await response.json();
    return configData;
  } catch (error) {
    console.error(error);
  }
};
