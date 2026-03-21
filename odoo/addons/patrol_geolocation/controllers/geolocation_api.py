"""
Geolocation API — AI ส่ง detection + bounding box → ได้พิกัดจริงกลับไป

Flow:
  1. AI ตรวจจับวัตถุ → ส่ง camera_name + bbox (pixel coordinates)
  2. ระบบหา calibration ของกล้อง
  3. แปลง pixel → พิกัดจริง (เลือกวิธีที่ดีที่สุด)
  4. Sensor Fusion: ถ้า match ทหารที่มี GPS → ใช้ GPS จริง
  5. อัพเดท/สร้าง world track
  6. Return พิกัดจริงกลับ
"""

from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-Patrol-Api-Key"


def _check_api_key():
    key = request.httprequest.headers.get(API_KEY_HEADER)
    expected = request.env["ir.config_parameter"].sudo().get_param("patrol.api_key", "patrol-secret-key")
    return key == expected


class GeolocationAPIController(http.Controller):

    @http.route("/patrol/api/external/geolocate", type="json", auth="none", csrf=False)
    def geolocate_detection(self, camera_name, object_type, bbox_x, bbox_y, bbox_w=0, bbox_h=0,
                            track_id=None, person_match_id=None, plate_number=None,
                            confidence=0, snapshot_base64=None):
        """
        AI ส่ง detection → ได้พิกัดจริงกลับ

        Args:
            camera_name: equipment.name
            object_type: "person" / "vehicle"
            bbox_x, bbox_y: จุดกลาง bottom ของ bounding box (pixel)
            bbox_w, bbox_h: ขนาด bbox
            track_id: AI tracking ID (ข้ามกล้อง)
            person_match_id: patrol.access.person.id
            plate_number: ทะเบียน
            confidence: 0-100

        Returns:
            lat, lng, accuracy, source, track_id
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)

        # หากล้อง
        equipment = env["patrol.equipment"].search([("name", "=", camera_name)], limit=1)
        if not equipment:
            return {"error": f"camera not found: {camera_name}"}

        # ─── Step 1: หา calibration ───
        calib = env["patrol.camera.calibration"].search([
            ("equipment_id", "=", equipment.id),
            ("is_active", "=", True),
        ], limit=1)

        # ─── Step 2: แปลง pixel → พิกัดจริง ───
        world_pos = None
        position_source = "camera_fallback"

        # วิธี A: Sensor Fusion — ถ้า match ทหารที่มี GPS จาก Socket.IO
        if person_match_id:
            person = env["patrol.access.person"].browse(int(person_match_id))
            if person.exists() and person.soldier_id and person.soldier_id.is_online:
                soldier = person.soldier_id
                if soldier.last_lat and soldier.last_lng:
                    world_pos = {
                        "lat": soldier.last_lat,
                        "lng": soldier.last_lng,
                        "accuracy": 5.0,  # GPS accuracy ~5m
                        "method": "gps_fusion",
                    }
                    position_source = "gps_fusion"
                    _logger.info("GPS Fusion: %s → soldier %s GPS", camera_name, soldier.callsign)

        # วิธี B: Camera Calibration (Homography / Parameters)
        if not world_pos and calib:
            # ใช้จุดล่าง-กลางของ bbox (ตำแหน่งเท้า/ล้อ)
            foot_x = bbox_x + bbox_w / 2 if bbox_w else bbox_x
            foot_y = bbox_y + bbox_h if bbox_h else bbox_y

            world_pos = calib.pixel_to_world(foot_x, foot_y)
            if world_pos:
                position_source = world_pos.get("method", "camera_params")

        # วิธี C: Fallback — ใช้พิกัดกล้อง
        if not world_pos:
            world_pos = {
                "lat": equipment.gps_lat,
                "lng": equipment.gps_lng,
                "accuracy": 50.0,
                "method": "camera_fallback",
            }
            position_source = "camera_fallback"

        lat = world_pos["lat"]
        lng = world_pos["lng"]
        accuracy = world_pos.get("accuracy", 50.0)

        # ─── Step 3: Match status ───
        match_status = "unknown"
        person = None
        vehicle = None
        soldier = None

        if person_match_id:
            person = env["patrol.access.person"].browse(int(person_match_id))
            if person.exists():
                match_status = "known"
                if person.person_type == "blocked":
                    match_status = "watchlist"
                if person.soldier_id:
                    soldier = person.soldier_id

        if plate_number:
            vehicle = env["patrol.access.vehicle"].search([("plate_number", "=", plate_number)], limit=1)
            if vehicle:
                match_status = "known"
                if vehicle.vehicle_type == "blocked":
                    match_status = "watchlist"

        # ─── Step 4: อัพเดท/สร้าง World Track ───
        import base64
        snapshot_binary = base64.b64decode(snapshot_base64) if snapshot_base64 else None

        track = None
        if track_id:
            track = env["patrol.world.track"].search([("track_id", "=", track_id)], limit=1)

        if track:
            # อัพเดท track ที่มีอยู่
            cameras = set((track.cameras_seen or "").split(","))
            cameras.add(str(equipment.id))
            cameras.discard("")

            track.write({
                "lat": lat,
                "lng": lng,
                "accuracy": accuracy,
                "position_source": position_source,
                "last_seen": fields.Datetime.now(),
                "cameras_seen": ",".join(cameras),
                "match_status": match_status,
                "person_id": person.id if person else track.person_id.id,
                "vehicle_id": vehicle.id if vehicle else track.vehicle_id.id,
                "soldier_id": soldier.id if soldier else track.soldier_id.id,
                "detected_plate": plate_number or track.detected_plate,
                "snapshot": snapshot_binary or track.snapshot,
            })
        else:
            # สร้าง track ใหม่
            track_id = track_id or f"TRK-{equipment.id}-{fields.Datetime.now().strftime('%H%M%S%f')}"
            track = env["patrol.world.track"].create({
                "track_id": track_id,
                "object_type": object_type,
                "match_status": match_status,
                "person_id": person.id if person else False,
                "vehicle_id": vehicle.id if vehicle else False,
                "soldier_id": soldier.id if soldier else False,
                "detected_plate": plate_number,
                "lat": lat,
                "lng": lng,
                "accuracy": accuracy,
                "position_source": position_source,
                "cameras_seen": str(equipment.id),
                "snapshot": snapshot_binary,
            })

        # เพิ่ม track point
        env["patrol.world.track.point"].create({
            "track_id_rel": track.id,
            "equipment_id": equipment.id,
            "lat": lat,
            "lng": lng,
            "accuracy": accuracy,
            "position_source": position_source,
            "confidence": confidence,
            "bbox": f"{bbox_x},{bbox_y},{bbox_w},{bbox_h}",
        })

        return {
            "status": "ok",
            "lat": lat,
            "lng": lng,
            "accuracy": accuracy,
            "position_source": position_source,
            "track_id": track.track_id,
            "match_status": match_status,
        }

    @http.route("/patrol/api/world_tracks", type="json", auth="user")
    def get_world_tracks(self, active_only=True, minutes=10):
        """ดึง world tracks สำหรับแสดงบนแผนที่"""
        domain = []
        if active_only:
            domain.append(("is_active", "=", True))

        from datetime import timedelta
        if minutes:
            since = fields.Datetime.now() - timedelta(minutes=int(minutes))
            domain.append(("last_seen", ">=", since))

        tracks = request.env["patrol.world.track"].search_read(
            domain,
            ["track_id", "object_type", "match_status",
             "person_id", "vehicle_id", "soldier_id", "detected_plate",
             "lat", "lng", "accuracy", "position_source",
             "camera_count", "first_seen", "last_seen", "is_active"],
            order="last_seen desc",
            limit=200,
        )
        return tracks

    @http.route("/patrol/api/world_track_path", type="json", auth="user")
    def get_track_path(self, track_id, limit=500):
        """ดึงเส้นทางของ track"""
        track = request.env["patrol.world.track"].search([("track_id", "=", track_id)], limit=1)
        if not track:
            return []

        points = request.env["patrol.world.track.point"].search_read(
            [("track_id_rel", "=", track.id)],
            ["lat", "lng", "accuracy", "position_source", "equipment_id", "timestamp"],
            order="timestamp",
            limit=int(limit),
        )
        return points
