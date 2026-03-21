from odoo import models, fields, api


class Sighting(models.Model):
    _name = "patrol.sighting"
    _description = "บันทึกการพบเห็น คน/รถ จากกล้องในพื้นที่"
    _order = "timestamp desc"

    # Where / When
    equipment_id = fields.Many2one("patrol.equipment", string="กล้อง", required=True, index=True)
    timestamp = fields.Datetime(string="เวลา", default=fields.Datetime.now, index=True, required=True)
    lat = fields.Float(string="ละติจูด", digits=(10, 8), related="equipment_id.gps_lat", store=True)
    lng = fields.Float(string="ลองจิจูด", digits=(10, 8), related="equipment_id.gps_lng", store=True)

    # What
    sighting_type = fields.Selection(
        [("person", "บุคคล"), ("vehicle", "ยานพาหนะ"), ("vessel", "เรือ")],
        string="ประเภท",
        required=True,
    )

    # Match result
    match_status = fields.Selection(
        [
            ("known", "รู้จัก"),
            ("unknown", "ไม่รู้จัก"),
            ("watchlist", "ตรง Watchlist"),
        ],
        string="สถานะ",
        required=True,
        index=True,
    )

    # Person
    person_id = fields.Many2one("patrol.access.person", string="บุคคลที่ match")
    person_name = fields.Char(string="ชื่อ (ถ้ารู้จัก)", compute="_compute_display_name_ext", store=True)

    # Vehicle
    vehicle_id = fields.Many2one("patrol.access.vehicle", string="รถที่ match")
    detected_plate = fields.Char(string="ทะเบียนที่อ่านได้", index=True)

    # Watchlist
    watchlist_id = fields.Many2one("patrol.watchlist", string="ตรง Watchlist")
    incident_id = fields.Many2one("patrol.incident", string="Incident ที่สร้าง")

    # AI
    confidence = fields.Float(string="ความมั่นใจ AI (%)")
    snapshot = fields.Binary(string="ภาพจากกล้อง", attachment=True)
    bbox = fields.Char(string="Bounding Box (JSON)")

    # Tracking
    track_id = fields.Char(string="Track ID", index=True,
                           help="ID เดียวกันสำหรับคน/รถเดียวกันที่เห็นจากหลายกล้อง")
    direction = fields.Selection(
        [("entering", "เข้าพื้นที่"), ("leaving", "ออกจากพื้นที่"), ("passing", "ผ่าน"), ("stationary", "หยุดอยู่")],
        string="ทิศทาง",
    )

    note = fields.Text(string="หมายเหตุ")

    @api.depends("person_id", "vehicle_id", "match_status", "detected_plate")
    def _compute_display_name_ext(self):
        for rec in self:
            if rec.person_id:
                rec.person_name = rec.person_id.name
            elif rec.vehicle_id:
                rec.person_name = rec.vehicle_id.plate_number
            elif rec.detected_plate:
                rec.person_name = rec.detected_plate
            else:
                rec.person_name = "ไม่รู้จัก"


class SightingAlert(models.Model):
    _name = "patrol.sighting.alert"
    _description = "กฎแจ้งเตือนจากการพบเห็น"
    _order = "name"

    name = fields.Char(string="ชื่อกฎ", required=True)
    alert_type = fields.Selection(
        [
            ("watchlist", "ตรง Watchlist"),
            ("unknown_person", "พบบุคคลไม่รู้จัก"),
            ("unknown_vehicle", "พบรถไม่รู้จัก"),
            ("unknown_vessel", "พบเรือไม่รู้จัก"),
            ("blocked", "พบบุคคล/รถ/เรือ ต้องห้าม"),
            ("specific_person", "พบบุคคลที่กำหนด"),
            ("specific_vehicle", "พบรถ/เรือที่กำหนด"),
            ("crowd", "พบคนจำนวนมาก"),
            ("vessel_activity", "กิจกรรมทางน้ำผิดปกติ"),
        ],
        string="แจ้งเตือนเมื่อ",
        required=True,
    )
    equipment_ids = fields.Many2many("patrol.equipment", string="กล้องที่ใช้ (ว่าง = ทุกกล้อง)")
    person_id = fields.Many2one("patrol.access.person", string="บุคคลที่กำหนด")
    vehicle_id = fields.Many2one("patrol.access.vehicle", string="รถที่กำหนด")
    create_incident = fields.Boolean(string="สร้าง Incident อัตโนมัติ", default=True)
    severity = fields.Selection(
        [("low", "ต่ำ"), ("medium", "ปานกลาง"), ("high", "สูง"), ("critical", "วิกฤต")],
        string="ความรุนแรง",
        default="high",
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string="หมายเหตุ")
