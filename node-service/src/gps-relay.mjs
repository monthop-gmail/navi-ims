/**
 * GPS Relay — Socket.IO server
 *
 * ทหารส่ง GPS จากมือถือ → Socket.IO → relay ไป Odoo + broadcast ไป Center
 *
 * Events (from soldier):
 *   soldier:join    { callsign, name }
 *   soldier:gps     { lat, lng, accuracy }
 *   soldier:sos     { lat, lng }
 *   soldier:sos-cancel
 *
 * Events (broadcast to center):
 *   soldier:position  { callsign, lat, lng, accuracy, timestamp }
 *   soldier:online    { callsign }
 *   soldier:offline   { callsign }
 *   soldier:sos       { callsign, lat, lng }
 */

import { Server } from "socket.io";

const ODOO_URL = process.env.ODOO_URL || "http://odoo:8069";
const PATROL_API_KEY = process.env.PATROL_API_KEY || "patrol-secret-key";

// GPS buffer — batch ส่ง Odoo ทุก 2 วินาที (ลด HTTP calls)
let gpsBuffer = [];
let flushInterval = null;

/**
 * เรียก Odoo JSON-RPC (external API)
 */
async function callOdoo(endpoint, params) {
  try {
    const resp = await fetch(`${ODOO_URL}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Patrol-Api-Key": PATROL_API_KEY,
      },
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
    });
    const data = await resp.json();
    if (data.error) {
      console.error(`[ODOO ERROR] ${endpoint}:`, data.error);
    }
    return data.result;
  } catch (err) {
    console.error(`[ODOO FAIL] ${endpoint}:`, err.message);
    return null;
  }
}

/**
 * Flush GPS buffer → ส่ง batch ไป Odoo
 */
async function flushGpsBuffer() {
  if (gpsBuffer.length === 0) return;

  const entries = [...gpsBuffer];
  gpsBuffer = [];

  await callOdoo("/patrol/api/external/gps_batch", { entries });
}

/**
 * Attach Socket.IO to HTTP server
 */
export function setupGpsRelay(httpServer) {
  const io = new Server(httpServer, {
    cors: { origin: "*" },
    path: "/socket.io",
  });

  // Start GPS buffer flush interval
  flushInterval = setInterval(flushGpsBuffer, 2000);

  io.on("connection", (socket) => {
    console.log(`[WS] connected: ${socket.id}`);

    // ── ทหารเข้าร่วมระบบ ──
    socket.on("soldier:join", async (data) => {
      const { callsign, name } = data;
      if (!callsign) return;

      socket.callsign = callsign;
      socket.soldierName = name || callsign;

      // แจ้ง Odoo ว่า online
      await callOdoo("/patrol/api/external/soldier_status", {
        callsign,
        is_online: true,
        stream_path: callsign,
      });

      // Broadcast
      socket.broadcast.emit("soldier:online", { callsign, name: socket.soldierName });
      socket.emit("soldier:registered", { callsign, name: socket.soldierName });

      console.log(`[JOIN] ${callsign} (${socket.soldierName})`);
    });

    // ── GPS update ──
    socket.on("soldier:gps", (data) => {
      if (!socket.callsign) return;
      const { lat, lng, accuracy, altitude, speed } = data;

      // Buffer สำหรับส่ง Odoo เป็น batch
      gpsBuffer.push({
        callsign: socket.callsign,
        lat,
        lng,
        accuracy,
        altitude,
        speed,
      });

      // Broadcast ไป center ทันที (real-time)
      io.emit("soldier:position", {
        callsign: socket.callsign,
        name: socket.soldierName,
        lat,
        lng,
        accuracy,
        timestamp: new Date().toISOString(),
      });
    });

    // ── SOS ──
    socket.on("soldier:sos", async (data) => {
      if (!socket.callsign) return;
      const { lat, lng } = data;

      // สร้าง incident ใน Odoo
      const result = await callOdoo("/patrol/api/external/sos", {
        callsign: socket.callsign,
        lat,
        lng,
      });

      // Broadcast SOS
      io.emit("soldier:sos", {
        callsign: socket.callsign,
        name: socket.soldierName,
        lat,
        lng,
        incidentId: result?.incident_id,
        timestamp: new Date().toISOString(),
      });

      console.log(`[SOS] ${socket.callsign} at ${lat},${lng}`);
    });

    // ── SOS cancel ──
    socket.on("soldier:sos-cancel", () => {
      if (!socket.callsign) return;
      io.emit("soldier:sos-cancel", { callsign: socket.callsign });
      console.log(`[SOS-CANCEL] ${socket.callsign}`);
    });

    // ── Disconnect ──
    socket.on("disconnect", async () => {
      if (!socket.callsign) return;

      await callOdoo("/patrol/api/external/soldier_status", {
        callsign: socket.callsign,
        is_online: false,
      });

      io.emit("soldier:offline", { callsign: socket.callsign });
      console.log(`[LEFT] ${socket.callsign}`);
    });
  });

  return io;
}
