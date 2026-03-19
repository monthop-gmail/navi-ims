/**
 * Camera Ingest Service
 *
 * - รับ snapshot จากกล้องผ่าน HTTP POST
 * - ใส่คิว Bull เพื่อส่งต่อให้ Celery วิเคราะห์
 * - รับ webhook จากกล้อง (motion detect, etc.)
 */

import express from "express";
import { Queue, Worker } from "bullmq";
import IORedis from "ioredis";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";

const REDIS_URL = process.env.REDIS_URL || "redis://redis:6379/0";
const INNGEST_API_URL = process.env.INNGEST_API_URL || "http://inngest:8288";
const INNGEST_EVENT_KEY = process.env.INNGEST_EVENT_KEY || "";
const MEDIA_DIR = "/media/snapshots";

// ─── Redis Connection ───

const connection = new IORedis(REDIS_URL, { maxRetriesPerRequest: null });

// ─── Bull Queues ───

const cameraQueue = new Queue("camera-frames", { connection });

// ─── Worker: รับ frame แล้วบันทึก + ส่งเข้าคิว Celery ───

const frameWorker = new Worker(
  "camera-frames",
  async (job) => {
    const { cameraId, timestamp, imageBase64 } = job.data;

    // บันทึกไฟล์
    const dateDir = new Date(timestamp).toISOString().split("T")[0];
    const dir = join(MEDIA_DIR, cameraId, dateDir);
    await mkdir(dir, { recursive: true });

    const filename = `${timestamp.replace(/[:.]/g, "-")}.jpg`;
    const filepath = join(dir, filename);

    await writeFile(filepath, Buffer.from(imageBase64, "base64"));

    // ส่งไป Celery ผ่าน Redis (Celery protocol)
    // ใช้วิธีง่าย: ส่ง event ไป Inngest แล้วให้ Inngest สั่ง Celery
    // หรือจะ push ตรงเข้า Celery queue ก็ได้

    await sendCeleryTask("tasks.analyze_frame", [filepath, cameraId]);

    return { filepath, cameraId };
  },
  {
    connection,
    concurrency: 10, // process 10 frame พร้อมกัน
    limiter: {
      max: 100,
      duration: 1000, // ไม่เกิน 100 jobs/วินาที
    },
  }
);

frameWorker.on("completed", (job) => {
  console.log(`[OK] camera=${job.data.cameraId} processed`);
});

frameWorker.on("failed", (job, err) => {
  console.error(`[FAIL] camera=${job?.data?.cameraId}`, err.message);
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

  // Celery อ่านจาก Redis list ชื่อ "celery"
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

// ─── Express API ───

const app = express();
app.use(express.json({ limit: "10mb" }));

/**
 * POST /api/camera/snapshot
 * รับ snapshot จากกล้อง
 * Body: { cameraId: "cam-01", imageBase64: "..." }
 */
app.post("/api/camera/snapshot", async (req, res) => {
  const { cameraId, imageBase64 } = req.body;

  if (!cameraId || !imageBase64) {
    return res.status(400).json({ error: "cameraId and imageBase64 required" });
  }

  const job = await cameraQueue.add(
    "frame",
    {
      cameraId,
      timestamp: new Date().toISOString(),
      imageBase64,
    },
    {
      removeOnComplete: 1000, // เก็บ 1000 jobs ล่าสุด
      removeOnFail: 5000,
      attempts: 3,
      backoff: { type: "exponential", delay: 1000 },
    }
  );

  res.json({ jobId: job.id, status: "queued" });
});

/**
 * POST /api/camera/webhook
 * รับ event จากกล้อง (motion detect, tamper, etc.)
 */
app.post("/api/camera/webhook", async (req, res) => {
  const { cameraId, eventType, imageBase64 } = req.body;

  // ส่ง event ตรงไป Inngest
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
 * ดูสถานะคิว
 */
app.get("/api/queue/stats", async (req, res) => {
  const counts = await cameraQueue.getJobCounts();
  res.json(counts);
});

app.get("/health", (req, res) => res.json({ status: "ok" }));

app.listen(3000, () => {
  console.log("Camera Ingest Service running on :3000");
});
