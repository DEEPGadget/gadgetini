export async function fetchUsername() {
  try {
    const response = await fetch("/api/username");
    const data = await response.json();
    setUsername(data.username);
  } catch (error) {
    console.error("Failed to fetch username:", error);
  }
}
