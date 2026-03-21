"""
World Track — ติดตามวัตถุข้ามหลายกล้อง ด้วยพิกัดจริง

Features:
  1. รับ detection จาก AI + bounding box → แปลงเป็นพิกัดจริง
  2. จับกลุ่ม detection เดียวกัน (same person/vehicle) ข้ามกล้อง
  3. Sensor Fusion: ถ้ารู้จัก + มี GPS จากมือถือ → ใช้ GPS จริงแทน
  4. สร้าง path ย้อนหลัง (object trajectory)
"""

from odoo import models, fields, api


class WorldTrack(models.Model):
    _name = "patrol.world.track"
    _description = "ติดตามวัตถุด้วยพิกัดจริง"
    _order = "last_seen desc"

    track_id = fields.Char(string="Track ID", required=True, index=True,
                           help="AI กำหนด — วัตถุเดียวกันใช้ ID เดียวกันข้ามกล้อง")
    object_type = fields.Selection(
        [("person", "บุคคล"), ("vehicle", "ยานพาหนะ"), ("other", "อื่นๆ")],
        string="ประเภท",
        required=True,
    )
    match_status = fields.Selection(
        [("known", "รู้จัก"), ("unknown", "ไม่รู้จัก"), ("watchlist", "Watchlist")],
        string="สถานะ",
        default="unknown",
    )

    # Match results
    person_id = fields.Many2one("patrol.access.person", string="บุคคล")
    vehicle_id = fields.Many2one("patrol.access.vehicle", string="ยานพาหนะ")
    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร (ถ้า match)")
    detected_plate = fields.Char(string="ทะเบียน")

    # Current position (latest)
    lat = fields.Float(string="ละติจูดปัจจุบัน", digits=(10, 8))
    lng = fields.Float(string="ลองจิจูดปัจจุบัน", digits=(10, 8))
    accuracy = fields.Float(string="ความแม่น (เมตร)")
    position_source = fields.Selection(
        [
            ("camera_params", "Camera Parameters"),
            ("homography", "Homography"),
            ("multi_camera", "Multi-Camera Triangulation"),
            ("gps_fusion", "GPS Fusion (มือถือ)"),
            ("camera_fallback", "พิกัดกล้อง (fallback)"),
        ],
        string="แหล่งพิกัด",
    )

    # Tracking
    first_seen = fields.Datetime(string="เห็นครั้งแรก", default=fields.Datetime.now)
    last_seen = fields.Datetime(string="เห็นล่าสุด", default=fields.Datetime.now)
    cameras_seen = fields.Char(string="กล้องที่เห็น", help="comma-separated equipment IDs")
    camera_count = fields.Integer(string="จำนวนกล้อง", compute="_compute_camera_count")

    # Trail
    point_ids = fields.One2many("patrol.world.track.point", "track_id_rel", string="เส้นทาง")
    point_count = fields.Integer(compute="_compute_point_count")

    # Status
    is_active = fields.Boolean(string="ยังอยู่ในพื้นที่", default=True)
    snapshot = fields.Binary(string="ภาพล่าสุด", attachment=True)

    @api.depends("cameras_seen")
    def _compute_camera_count(self):
        for rec in self:
            if rec.cameras_seen:
                rec.camera_count = len(set(rec.cameras_seen.split(",")))
            else:
                rec.camera_count = 0

    @api.depends("point_ids")
    def _compute_point_count(self):
        for rec in self:
            rec.point_count = len(rec.point_ids)


class WorldTrackPoint(models.Model):
    _name = "patrol.world.track.point"
    _description = "จุดเส้นทางของ track"
    _order = "timestamp"

    track_id_rel = fields.Many2one("patrol.world.track", string="Track", required=True, ondelete="cascade")
    equipment_id = fields.Many2one("patrol.equipment", string="กล้อง")
    timestamp = fields.Datetime(string="เวลา", default=fields.Datetime.now, required=True)
    lat = fields.Float(string="ละติจูด", digits=(10, 8), required=True)
    lng = fields.Float(string="ลองจิจูด", digits=(10, 8), required=True)
    accuracy = fields.Float(string="ความแม่น (เมตร)")
    position_source = fields.Selection(
        [
            ("camera_params", "Camera Parameters"),
            ("homography", "Homography"),
            ("multi_camera", "Multi-Camera"),
            ("gps_fusion", "GPS Fusion"),
            ("camera_fallback", "พิกัดกล้อง"),
        ],
        string="แหล่งพิกัด",
    )
    confidence = fields.Float(string="ความมั่นใจ AI (%)")
    bbox = fields.Char(string="Bounding Box")
