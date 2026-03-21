from odoo import models, fields


class AccessLog(models.Model):
    _name = "patrol.access.log"
    _description = "บันทึกเข้า-ออก"
    _order = "timestamp desc"

    gate_id = fields.Many2one("patrol.access.gate", string="ประตู", required=True, index=True)
    direction = fields.Selection(
        [("in", "เข้า"), ("out", "ออก")],
        string="ทิศทาง",
        required=True,
    )
    access_type = fields.Selection(
        [("person", "บุคคล"), ("vehicle", "ยานพาหนะ")],
        string="ประเภท",
    )
    result = fields.Selection(
        [
            ("auto_granted", "อนุญาตอัตโนมัติ (รู้จัก)"),
            ("manual_granted", "อนุญาตโดยเจ้าหน้าที่"),
            ("denied", "ปฏิเสธ"),
            ("blocked", "บล็อก (ต้องห้าม)"),
            ("timeout", "หมดเวลา"),
        ],
        string="ผลลัพธ์",
    )

    # Who
    person_id = fields.Many2one("patrol.access.person", string="บุคคล")
    vehicle_id = fields.Many2one("patrol.access.vehicle", string="ยานพาหนะ")
    detected_plate = fields.Char(string="ทะเบียนที่ตรวจจับ")

    # AI
    match_confidence = fields.Float(string="ความมั่นใจ AI (%)")
    snapshot_image = fields.Binary(string="ภาพจากกล้อง", attachment=True)

    # Time
    timestamp = fields.Datetime(string="เวลา", default=fields.Datetime.now, index=True)
    request_id = fields.Many2one("patrol.access.request", string="คำขอ (ถ้ามี)")
