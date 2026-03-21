"""
Camera Calibration — ข้อมูลกล้องสำหรับแปลง pixel → พิกัดจริง

รองรับ 2 วิธี:
  1. Homography Matrix (4 จุด calibration → คำนวณ projection)
  2. Camera Parameters (ตำแหน่ง + ทิศ + FOV + ความสูง + มุมก้ม)
"""

from odoo import models, fields, api
import json
import math


class CameraCalibration(models.Model):
    _name = "patrol.camera.calibration"
    _description = "Camera Calibration สำหรับแปลง pixel → พิกัดจริง"
    _inherit = ["mail.thread"]

    equipment_id = fields.Many2one("patrol.equipment", string="กล้อง", required=True, ondelete="cascade")
    name = fields.Char(string="ชื่อ", compute="_compute_name", store=True)
    method = fields.Selection(
        [
            ("params", "Camera Parameters (ตำแหน่ง+ทิศ+FOV)"),
            ("homography", "Homography Matrix (4 จุด calibration)"),
        ],
        string="วิธี Calibration",
        default="params",
        required=True,
    )
    is_active = fields.Boolean(string="ใช้งาน", default=True)

    # ─── Method 1: Camera Parameters ───
    cam_lat = fields.Float(string="ละติจูดกล้อง", digits=(10, 8))
    cam_lng = fields.Float(string="ลองจิจูดกล้อง", digits=(10, 8))
    cam_height = fields.Float(string="ความสูงกล้อง (เมตร)", default=5.0, help="ความสูงจากพื้น")
    cam_heading = fields.Float(string="ทิศที่หัน (องศา)", help="0=เหนือ, 90=ตะวันออก, 180=ใต้, 270=ตะวันตก")
    cam_tilt = fields.Float(string="มุมก้ม (องศา)", default=30.0, help="0=มองตรง, 90=มองลงดิ่ง")
    cam_fov_h = fields.Float(string="มุมมองแนวนอน (องศา)", default=90.0)
    cam_fov_v = fields.Float(string="มุมมองแนวตั้ง (องศา)", default=60.0)
    image_width = fields.Integer(string="ความกว้างภาพ (px)", default=1920)
    image_height = fields.Integer(string="ความสูงภาพ (px)", default=1080)

    # ─── Method 2: Homography (4 จุด) ───
    # จุด calibration: pixel (x,y) → GPS (lat,lng)
    calib_points_json = fields.Text(
        string="จุด Calibration (JSON)",
        help='[{"px":100,"py":200,"lat":13.756,"lng":100.501}, ...]  ต้อง 4 จุดขึ้นไป',
    )
    homography_matrix = fields.Text(string="Homography Matrix (JSON)", readonly=True,
                                    help="คำนวณอัตโนมัติจากจุด calibration")

    # ─── Max Range ───
    max_range = fields.Float(string="ระยะสูงสุดที่แม่น (เมตร)", default=100.0)
    accuracy_estimate = fields.Float(string="ความแม่นโดยประมาณ (เมตร)", default=10.0)

    @api.depends("equipment_id")
    def _compute_name(self):
        for rec in self:
            rec.name = f"Calibration — {rec.equipment_id.name}" if rec.equipment_id else "New"

    def action_compute_homography(self):
        """คำนวณ Homography Matrix จาก calibration points"""
        for rec in self:
            if not rec.calib_points_json:
                continue
            points = json.loads(rec.calib_points_json)
            if len(points) < 4:
                continue
            # Store for use by Celery worker
            # Actual homography computation done in Python/NumPy on Celery side
            rec.homography_matrix = json.dumps({
                "points": points,
                "status": "ready",
                "method": "perspective_transform",
            })

    def pixel_to_world(self, px, py):
        """
        แปลง pixel (x, y) ในภาพ → พิกัด GPS (lat, lng)

        ใช้วิธี Camera Parameters:
          1. คำนวณมุม azimuth + elevation จาก pixel position
          2. Project ลงพื้นตามความสูง + มุมก้ม
          3. แปลง distance + bearing → lat/lng
        """
        self.ensure_one()

        if self.method == "params":
            return self._pixel_to_world_params(px, py)
        elif self.method == "homography":
            return self._pixel_to_world_homography(px, py)
        return None

    def _pixel_to_world_params(self, px, py):
        """แปลงด้วย Camera Parameters"""
        # Normalize pixel to [-1, 1]
        nx = (px / self.image_width - 0.5) * 2   # -1 (ซ้าย) ถึง 1 (ขวา)
        ny = (py / self.image_height - 0.5) * 2  # -1 (บน) ถึง 1 (ล่าง)

        # คำนวณ azimuth offset จาก center
        azimuth_offset = nx * (self.cam_fov_h / 2)
        bearing = (self.cam_heading + azimuth_offset) % 360

        # คำนวณ elevation offset → ระยะทาง
        elevation_offset = ny * (self.cam_fov_v / 2)
        look_angle = self.cam_tilt + elevation_offset  # มุมจากแนวนอน

        if look_angle <= 0:
            return None  # มองเหนือขอบฟ้า

        # ระยะบนพื้น = ความสูง / tan(มุมก้ม)
        distance = self.cam_height / math.tan(math.radians(look_angle))
        distance = min(distance, self.max_range)

        # แปลง distance + bearing → lat/lng offset
        lat, lng = self._offset_latlng(self.cam_lat, self.cam_lng, distance, bearing)

        return {
            "lat": round(lat, 8),
            "lng": round(lng, 8),
            "distance": round(distance, 1),
            "bearing": round(bearing, 1),
            "accuracy": round(self.accuracy_estimate + distance * 0.1, 1),
            "method": "camera_params",
        }

    def _pixel_to_world_homography(self, px, py):
        """แปลงด้วย Homography Matrix (linear interpolation fallback)"""
        if not self.homography_matrix:
            return None

        data = json.loads(self.homography_matrix)
        points = data.get("points", [])
        if len(points) < 4:
            return None

        # Simple bilinear interpolation (Celery ทำ proper homography ได้)
        total_weight = 0
        lat_sum = 0
        lng_sum = 0

        for p in points:
            dx = px - p["px"]
            dy = py - p["py"]
            dist = math.sqrt(dx * dx + dy * dy) + 1  # avoid div by 0
            weight = 1.0 / dist
            lat_sum += p["lat"] * weight
            lng_sum += p["lng"] * weight
            total_weight += weight

        return {
            "lat": round(lat_sum / total_weight, 8),
            "lng": round(lng_sum / total_weight, 8),
            "accuracy": round(self.accuracy_estimate, 1),
            "method": "homography_interpolation",
        }

    @staticmethod
    def _offset_latlng(lat, lng, distance_m, bearing_deg):
        """คำนวณ lat/lng ใหม่จากจุดเดิม + ระยะ + ทิศ"""
        R = 6371000  # รัศมีโลก (เมตร)
        lat_r = math.radians(lat)
        lng_r = math.radians(lng)
        bearing_r = math.radians(bearing_deg)
        d_r = distance_m / R

        new_lat = math.asin(
            math.sin(lat_r) * math.cos(d_r) +
            math.cos(lat_r) * math.sin(d_r) * math.cos(bearing_r)
        )
        new_lng = lng_r + math.atan2(
            math.sin(bearing_r) * math.sin(d_r) * math.cos(lat_r),
            math.cos(d_r) - math.sin(lat_r) * math.sin(new_lat)
        )

        return math.degrees(new_lat), math.degrees(new_lng)
