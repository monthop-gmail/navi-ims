/**
 * Camera Ingest Service
 *
 * ดึง frame จากกล้อง 3 ประเภทผ่าน MediaMTX (RTSP):
 *   - Fixed cam (Dahua NVR) → RTSP 24/7
 *   - Drone cam → RTMP push → MediaMTX → RTSP
 *   - Body cam (ทหาร) → WebRTC push → MediaMTX → RTSP
 *
 * ใช้ FFmpeg ดึง snapshot จาก RTSP → ส่งเข้า Bull queue → Celery AI วิเคราะห์
 */

import express from "express";
import { Queue, Worker } from "bullmq";
import IORedis from "ioredis";
import { writeFile, mkdir, readFile } from "fs/promises";
import { join } from "path";
import { spawn } from "child_process";
import { existsSync } from "fs";

const REDIS_URL = process.env.REDIS_URL || "redis://redis:6379/0";
const INNGEST_API_URL = process.env.INNGEST_API_URL || "http://inngest:8288";
const INNGEST_EVENT_KEY = process.env.INNGEST_EVENT_KEY || "";
const MEDIAMTX_API_URL = process.env.MEDIAMTX_API_URL || "http://mediamtx:9997";
const MEDIAMTX_RTSP_URL = process.env.MEDIAMTX_RTSP_URL || "rtsp://mediamtx:8554";
const MEDIA_DIR = "/media/snapshots";

// ─── Redis Connection ───

const connection = new IORedis(REDIS_URL, { maxRetriesPerRequest: null });

// ─── Bull Queues ───

const cameraQueue = new Queue("camera-frames", { connection });

// ─── Active RTSP pullers (จัดการ start/stop ต่อกล้อง) ───

const activePullers = new Map(); // cameraId → intervalId

/**
 * ดึง 1 frame จาก RTSP stream ด้วย FFmpeg
 * บันทึกเป็น .jpg แล้วส่งเข้า Bull queue
 */
async function captureFrame(cameraId, rtspPath) {
  const rtspUrl = `${MEDIAMTX_RTSP_URL}/${rtspPath}`;
  const timestamp = new Date().toISOString();
  const dateDir = timestamp.split("T")[0];
  const dir = join(MEDIA_DIR, cameraId, dateDir);
  await mkdir(dir, { recursive: true });

  const filename = `${timestamp.replace(/[:.]/g, "-")}.jpg`;
  const filepath = join(dir, filename);

  return new Promise((resolve, reject) => {
    const ffmpeg = spawn("ffmpeg", [
      "-y",
      "-rtsp_transport", "tcp",
      "-i", rtspUrl,
      "-frames:v", "1",
      "-q:v", "2",
      filepath,
    ], { timeout: 10000 });

    let stderr = "";
    ffmpeg.stderr.on("data", (d) => (stderr += d.toString()));

    ffmpeg.on("close", async (code) => {
      if (code !== 0 || !existsSync(filepath)) {
        reject(new Error(`FFmpeg failed for ${cameraId}: ${stderr.slice(-200)}`));
        return;
      }

      // ส่งเข้า Bull queue
      await cameraQueue.add("frame", {
        cameraId,
        rtspPath,
        timestamp,
        filepath,
      }, {
        removeOnComplete: 1000,
        removeOnFail: 5000,
        attempts: 3,
        backoff: { type: "exponential", delay: 1000 },
      });

      resolve(filepath);
    });
  });
}

/**
 * เริ่มดึง frame จากกล้อง 1 ตัวเป็นระยะ
 */
function startPuller(cameraId, rtspPath, intervalMs) {
  if (activePullers.has(cameraId)) {
    console.log(`[SKIP] ${cameraId} already pulling`);
    return;
  }

  console.log(`[START] ${cameraId} → ${rtspPath} every ${intervalMs}ms`);

  // ดึงทันทีรอบแรก
  captureFrame(cameraId, rtspPath).catch((e) =>
    console.error(`[ERR] ${cameraId}:`, e.message)
  );

  const intervalId = setInterval(() => {
    captureFrame(cameraId, rtspPath).catch((e) =>
      console.error(`[ERR] ${cameraId}:`, e.message)
    );
  }, intervalMs);

  activePullers.set(cameraId, intervalId);
}

/**
 * หยุดดึง frame จากกล้อง
 */
function stopPuller(cameraId) {
  const intervalId = activePullers.get(cameraId);
  if (intervalId) {
    clearInterval(intervalId);
    activePullers.delete(cameraId);
    console.log(`[STOP] ${cameraId}`);
  }
}

// ─── Worker: รับ frame path แล้วส่งเข้า Celery ───

const frameWorker = new Worker(
  "camera-frames",
  async (job) => {
    const { cameraId, filepath } = job.data;
    await sendCeleryTask("tasks.analyze_frame", [filepath, cameraId]);
    return { filepath, cameraId };
  },
  {
    connection,
    concurrency: 10,
    limiter: { max: 100, duration: 1000 },
  }
);

frameWorker.on("completed", (job) => {
  console.log(`[OK] ${job.data.cameraId} → Celery`);
});

frameWorker.on("failed", (job, err) => {
  console.error(`[FAIL] ${job?.data?.cameraId}`, err.message);
});

// ─── ส่ง task ตรงเข้า Celery queue ผ่าน Redis ───

async function sendCeleryTask(taskName, args) {
  const taskId = crypto.randomUUID();
  const message = {
    id: taskId,
    task: taskName,
    args: args,
    kwargs: {},
    retries: 0,
    eta: null,
  };

  await connection.lpush(
    "celery",
    JSON.stringify({
      body: Buffer.from(JSON.stringify(message)).toString("base64"),
      "content-encoding": "utf-8",
      "content-type": "application/json",
      headers: {
        task: taskName,
        id: taskId,
        lang: "py",
        root_id: taskId,
      },
      properties: {
        correlation_id: taskId,
        delivery_mode: 2,
        delivery_tag: taskId,
        body_encoding: "base64",
      },
    })
  );
}

// ─── Express API (Odoo เรียกเพื่อสั่งจัดการกล้อง) ───

const app = express();
app.use(express.json({ limit: "10mb" }));

/**
 * POST /api/camera/start
 * Odoo สั่งเริ่มดึง frame จากกล้อง
 * Body: { cameraId: "cam-01", rtspPath: "fixed/cam-01", intervalMs: 2000 }
 */
app.post("/api/camera/start", (req, res) => {
  const { cameraId, rtspPath, intervalMs = 2000 } = req.body;

  if (!cameraId || !rtspPath) {
    return res.status(400).json({ error: "cameraId and rtspPath required" });
  }

  startPuller(cameraId, rtspPath, intervalMs);
  res.json({ status: "started", cameraId, intervalMs });
});

/**
 * POST /api/camera/stop
 * Odoo สั่งหยุดดึง frame
 * Body: { cameraId: "cam-01" }
 */
app.post("/api/camera/stop", (req, res) => {
  const { cameraId } = req.body;
  stopPuller(cameraId);
  res.json({ status: "stopped", cameraId });
});

/**
 * GET /api/camera/active
 * ดูกล้องที่กำลัง pull อยู่
 */
app.get("/api/camera/active", (req, res) => {
  res.json({
    count: activePullers.size,
    cameras: [...activePullers.keys()],
  });
});

/**
 * GET /api/streams
 * ดูรายการ stream ทั้งหมดจาก MediaMTX
 */
app.get("/api/streams", async (req, res) => {
  try {
    const resp = await fetch(`${MEDIAMTX_API_URL}/v3/paths/list`);
    const data = await resp.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/**
 * POST /api/camera/webhook
 * รับ event จากกล้อง (motion detect, tamper, etc.)
 */
app.post("/api/camera/webhook", async (req, res) => {
  const { cameraId, eventType, imageBase64 } = req.body;

  await fetch(`${INNGEST_API_URL}/e/${INNGEST_EVENT_KEY}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: `camera.${eventType}`,
      data: { cameraId, eventType, imageBase64 },
    }),
  });

  res.json({ status: "event_sent" });
});

/**
 * GET /api/queue/stats
 */
app.get("/api/queue/stats", async (req, res) => {
  const counts = await cameraQueue.getJobCounts();
  res.json(counts);
});

app.get("/health", (req, res) => res.json({ status: "ok" }));

app.listen(3000, () => {
  console.log("Camera Ingest Service running on :3000");
  console.log(`MediaMTX RTSP: ${MEDIAMTX_RTSP_URL}`);
});
