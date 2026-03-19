/**
 * Bull Board — UI Dashboard สำหรับดูสถานะ Bull queues
 * เปิดที่ http://localhost:3100/
 */

import express from "express";
import { createBullBoard } from "@bull-board/api";
import { BullMQAdapter } from "@bull-board/api/bullMQAdapter.js";
import { ExpressAdapter } from "@bull-board/express";
import { Queue } from "bullmq";
import IORedis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://redis:6379/0";
const connection = new IORedis(REDIS_URL, { maxRetriesPerRequest: null });

const cameraQueue = new Queue("camera-frames", { connection });

const serverAdapter = new ExpressAdapter();
serverAdapter.setBasePath("/");

createBullBoard({
  queues: [new BullMQAdapter(cameraQueue)],
  serverAdapter,
});

const app = express();
app.use("/", serverAdapter.getRouter());

app.listen(3100, () => {
  console.log("Bull Board running on :3100");
});
