from odoo import models, fields, api


class AccessRequest(models.Model):
    _name = "patrol.access.request"
    _description = "คำขอเข้า-ออก (สำหรับคน/รถ ไม่รู้จัก)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_time desc"

    name = fields.Char(string="เรื่อง", compute="_compute_name", store=True)
    gate_id = fields.Many2one("patrol.access.gate", string="ประตู", required=True)
    request_type = fields.Selection(
        [("person", "บุคคล"), ("vehicle", "ยานพาหนะ")],
        string="ประเภท",
        required=True,
    )
    state = fields.Selection(
        [
            ("pending", "รออนุมัติ"),
            ("approved", "อนุมัติ"),
            ("denied", "ปฏิเสธ"),
            ("expired", "หมดเวลา"),
        ],
        string="สถานะ",
        default="pending",
        tracking=True,
    )

    # Who/What
    snapshot_image = fields.Binary(string="ภาพจากกล้อง", attachment=True)
    detected_plate = fields.Char(string="ทะเบียนที่ตรวจจับ")
    detected_description = fields.Text(string="รายละเอียดที่ AI ตรวจจับ")
    matched_person_id = fields.Many2one("patrol.access.person", string="บุคคลที่ตรงกัน (partial match)")
    matched_vehicle_id = fields.Many2one("patrol.access.vehicle", string="รถที่ตรงกัน (partial match)")
    match_confidence = fields.Float(string="ความมั่นใจ (%)")

    # Time
    request_time = fields.Datetime(string="เวลาขอ", default=fields.Datetime.now)
    response_time = fields.Datetime(string="เวลาตอบ")
    approved_by = fields.Many2one("res.users", string="อนุมัติโดย")

    # Resolution
    register_as_known = fields.Boolean(string="บันทึกเข้าฐานข้อมูล", default=False,
                                       help="ถ้าอนุมัติ จะบันทึกบุคคล/รถเข้าทะเบียนด้วย")
    note = fields.Text(string="หมายเหตุ")

    @api.depends("gate_id", "request_type", "detected_plate")
    def _compute_name(self):
        for rec in self:
            if rec.request_type == "vehicle" and rec.detected_plate:
                rec.name = f"[{rec.gate_id.name or ''}] รถ {rec.detected_plate}"
            else:
                rec.name = f"[{rec.gate_id.name or ''}] {rec.request_type or ''} ไม่รู้จัก"

    def action_approve(self):
        """อนุมัติ → เปิดประตู"""
        for rec in self:
            rec.write({
                "state": "approved",
                "approved_by": self.env.user.id,
                "response_time": fields.Datetime.now(),
            })
            # เปิดประตู
            if rec.gate_id:
                rec.gate_id.action_open()

            # บันทึกเข้าทะเบียน (ถ้าเลือก)
            if rec.register_as_known:
                rec._register_as_known()

    def action_deny(self):
        """ปฏิเสธ"""
        self.write({
            "state": "denied",
            "response_time": fields.Datetime.now(),
        })

    def _register_as_known(self):
        """บันทึกคน/รถที่อนุมัติเข้าทะเบียน"""
        self.ensure_one()
        if self.request_type == "vehicle" and self.detected_plate:
            self.env["patrol.access.vehicle"].create({
                "plate_number": self.detected_plate,
                "vehicle_type": "visitor",
                "photo": self.snapshot_image,
                "access_level": "specific",
                "allowed_gate_ids": [(4, self.gate_id.id)],
                "note": f"บันทึกจากคำขอเข้า-ออก เมื่อ {self.request_time}",
            })
        elif self.request_type == "person":
            self.env["patrol.access.person"].create({
                "name": self.note or "ไม่ทราบชื่อ",
                "person_type": "visitor",
                "photo": self.snapshot_image,
                "access_level": "specific",
                "allowed_gate_ids": [(4, self.gate_id.id)],
                "note": f"บันทึกจากคำขอเข้า-ออก เมื่อ {self.request_time}",
            })
