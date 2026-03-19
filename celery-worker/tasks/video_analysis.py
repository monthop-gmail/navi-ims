"""
Tasks สำหรับวิเคราะห์ภาพจากกล้อง + ตรวจสอบการแก้ไข
"""

import os
import cv2
import numpy as np
import httpx
from celery_app import app

INNGEST_API_URL = os.environ.get("INNGEST_API_URL", "http://inngest:8288")
INNGEST_EVENT_KEY = os.environ.get("INNGEST_EVENT_KEY", "")


def send_inngest_event(name: str, data: dict):
    """ส่ง event ไป Inngest Server"""
    httpx.post(
        f"{INNGEST_API_URL}/e/{INNGEST_EVENT_KEY}",
        json={"name": name, "data": data},
        timeout=10,
    )


@app.task(name="tasks.analyze_frame", bind=True, max_retries=3)
def analyze_frame(self, image_path: str, camera_id: str):
    """
    AI วิเคราะห์ภาพ 1 frame
    ตรวจจับ: คน, หมวกนิรภัย, ไฟ, ควัน ฯลฯ
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"status": "error", "reason": "cannot read image"}

        # ─── ตรวจจับด้วย YOLO ───
        # TODO: โหลด model จริง เช่น YOLOv8
        # from ultralytics import YOLO
        # model = YOLO("yolov8n.pt")
        # results = model.predict(image, conf=0.5)

        # ─── Placeholder: สุ่มจำลองการตรวจจับ ───
        anomalies = _detect_anomalies_placeholder(image)

        if anomalies:
            for anomaly in anomalies:
                send_inngest_event(
                    "anomaly.detected",
                    {
                        "camera_id": camera_id,
                        "type": anomaly["type"],
                        "confidence": anomaly["confidence"],
                        "image_path": image_path,
                        "bbox": anomaly.get("bbox"),
                    },
                )

        return {
            "status": "analyzed",
            "camera_id": camera_id,
            "anomalies_found": len(anomalies),
        }

    except Exception as exc:
        self.retry(exc=exc, countdown=5)


@app.task(name="tasks.verify_resolution", bind=True, max_retries=2)
def verify_resolution(self, proof_image_path: str, original_anomaly_type: str):
    """
    AI ตรวจสอบว่าปัญหาถูกแก้ไขจริงหรือยัง
    เช่น ส่งรูปมาว่าใส่หมวกแล้ว → AI ยืนยันว่าใส่จริง
    """
    try:
        image = cv2.imread(proof_image_path)
        if image is None:
            return {"passed": False, "reason": "cannot read proof image"}

        # TODO: ใช้ AI model จริงตรวจสอบ
        # ตัวอย่าง: ถ้า anomaly เดิมคือ "no_helmet"
        # → ตรวจว่าในรูปใหม่มีหมวกหรือยัง

        # Placeholder
        return {"passed": True, "reason": "verified by AI"}

    except Exception as exc:
        self.retry(exc=exc, countdown=5)


@app.task(name="tasks.encode_video")
def encode_video(input_path: str, output_path: str, resolution: str = "720p"):
    """Encode/transcode video ด้วย FFmpeg"""
    import subprocess

    height = resolution.replace("p", "")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return {"status": "done", "output": output_path}


@app.task(name="tasks.generate_thumbnail")
def generate_thumbnail(video_path: str, output_path: str, timestamp: str = "00:00:01"):
    """สร้าง thumbnail จาก video"""
    import subprocess

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", timestamp,
        "-vframes", "1",
        "-q:v", "2",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return {"status": "done", "output": output_path}


def _detect_anomalies_placeholder(image: np.ndarray) -> list:
    """
    Placeholder — จำลองผลการตรวจจับ
    ใน production ให้แทนที่ด้วย YOLO / custom model จริง
    """
    # สุ่ม 5% ว่าเจอความผิดปกติ (สำหรับทดสอบ)
    if np.random.random() < 0.05:
        return [
            {
                "type": "no_helmet",
                "confidence": round(float(np.random.uniform(0.7, 0.99)), 2),
                "bbox": [100, 200, 300, 400],
            }
        ]
    return []
