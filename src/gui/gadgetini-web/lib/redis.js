// Singleton Redis client for Next.js API routes.
// Same Redis instance as control_board / sensor_exporter (localhost:6379, db 0).
import Redis from "ioredis";

let _client = null;

export function getRedis() {
  if (!_client) {
    _client = new Redis({
      host: process.env.REDIS_HOST || "127.0.0.1",
      port: Number(process.env.REDIS_PORT || 6379),
      // Avoid noisy reconnect logs when control_board hasn't started.
      lazyConnect: false,
      maxRetriesPerRequest: 1,
    });
    _client.on("error", (err) => {
      // eslint-disable-next-line no-console
      console.warn("[redis] connection error:", err.message);
    });
  }
  return _client;
}
