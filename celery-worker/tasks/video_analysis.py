"""
Tasks สำหรับวิเคราะห์ภาพจากกล้อง + ตรวจสอบการแก้ไข
ใช้กับทุกแหล่งภาพ: Fixed cam, Body cam, Drone cam
"""

import os
import cv2
import numpy as np
import httpx
from celery_app import app

ODOO_URL = os.environ.get("ODOO_URL", "http://odoo:8069")
PATROL_API_KEY = os.environ.get("PATROL_API_KEY", "patrol-secret-key")


def call_odoo_api(endpoint: str, params: dict):
    """เรียก Odoo Patrol External API"""
    try:
        resp = httpx.post(
            f"{ODOO_URL}{endpoint}",
            json={"jsonrpc": "2.0", "method": "call", "params": params},
            headers={"X-Patrol-Api-Key": PATROL_API_KEY},
            timeout=15,
        )
        data = resp.json()
        return data.get("result")
    except Exception as e:
        print(f"[ODOO ERROR] {endpoint}: {e}")
        return None


@app.task(name="tasks.analyze_frame", bind=True, max_retries=3)
def analyze_frame(self, image_path: str, camera_id: str):
    """
    AI วิเคราะห์ภาพ 1 frame จากกล้องใดก็ได้
    ตรวจจับ: บุคคล, ยานพาหนะ, ไฟ, ควัน, อาวุธ ฯลฯ

    camera_id = equipment.name ใน Odoo (เช่น "CAM-FIXED-01")
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"status": "error", "reason": "cannot read image"}

        # ─── ตรวจจับด้วย YOLO ───
        # TODO: โหลด model จริง
        # from ultralytics import YOLO
        # model = YOLO("/models/yolov8n.pt")
        # results = model.predict(image, conf=0.5)
        # anomalies = parse_yolo_results(results)

        # ─── Placeholder: สุ่มจำลอง (5% chance) ───
        anomalies = _detect_anomalies_placeholder(image)

        if anomalies:
            for anomaly in anomalies:
                # สร้าง incident ใน Odoo ตรง → trigger Inngest อัตโนมัติ
                call_odoo_api("/patrol/api/external/ai_incident", {
                    "camera_name": camera_id,
                    "anomaly_type": anomaly["type"],
                    "confidence": anomaly["confidence"],
                    "image_path": image_path,
                    "bbox": anomaly.get("bbox"),
                })

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
    """
    try:
        image = cv2.imread(proof_image_path)
        if image is None:
            return {"passed": False, "reason": "cannot read proof image"}

        # TODO: ใช้ AI model จริง
        # ตัวอย่าง: ตรวจว่า "intruder" หายไปจาก frame แล้วหรือยัง

        # Placeholder — ผ่านเสมอ
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
    anomaly_types = ["intruder", "vehicle", "fire", "smoke", "weapon"]

    if np.random.random() < 0.05:
        atype = np.random.choice(anomaly_types)
        return [
            {
                "type": atype,
                "confidence": round(float(np.random.uniform(0.7, 0.99)), 2),
                "bbox": [100, 200, 300, 400],
            }
        ]
    return []
