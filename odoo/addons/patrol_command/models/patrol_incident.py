from odoo import models, fields, api


class PatrolIncident(models.Model):
    _name = "patrol.incident"
    _description = "เหตุการณ์ (Incident)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_reported desc"

    name = fields.Char(string="เหตุการณ์", required=True, tracking=True)
    incident_type = fields.Selection(
        [
            ("sos", "SOS ฉุกเฉิน"),
            ("ai_detection", "AI ตรวจจับ"),
            ("manual", "รายงานด้วยตนเอง"),
            ("geofence", "ออกนอกพื้นที่"),
        ],
        string="ประเภท",
        required=True,
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("low", "ต่ำ"),
            ("medium", "ปานกลาง"),
            ("high", "สูง"),
            ("critical", "วิกฤต"),
        ],
        string="ความรุนแรง",
        default="medium",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("new", "ใหม่"),
            ("assigned", "มอบหมายแล้ว"),
            ("in_progress", "กำลังดำเนินการ"),
            ("resolved", "แก้ไขแล้ว"),
            ("closed", "ปิด"),
        ],
        string="สถานะ",
        default="new",
        tracking=True,
    )
    priority = fields.Selection(
        [("0", "ปกติ"), ("1", "สำคัญ"), ("2", "เร่งด่วน"), ("3", "วิกฤต")],
        string="Priority",
        compute="_compute_priority",
        store=True,
    )

    # Who / Where
    soldier_id = fields.Many2one("patrol.soldier", string="ทหารที่เกี่ยวข้อง", tracking=True)
    equipment_id = fields.Many2one("patrol.equipment", string="กล้องที่ตรวจพบ")
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจ")
    lat = fields.Float(string="ละติจูด", digits=(10, 8))
    lng = fields.Float(string="ลองจิจูด", digits=(10, 8))

    # Detail
    description = fields.Html(string="รายละเอียด")
    ai_confidence = fields.Float(string="ความมั่นใจ AI (0-1)")
    ai_type = fields.Char(string="ประเภท AI", help="เช่น intruder, fire, no_helmet")
    image_ids = fields.Many2many(
        "ir.attachment", "patrol_incident_image_rel", "incident_id", "attachment_id",
        string="ภาพหลักฐาน",
    )

    # Assignment
    assigned_to = fields.Many2one("patrol.soldier", string="ผู้รับผิดชอบ", tracking=True)
    escalated_to = fields.Many2one("patrol.unit", string="หน่วยที่ Escalate")

    # Timeline
    date_reported = fields.Datetime(string="เวลาแจ้ง", default=fields.Datetime.now, required=True)
    date_assigned = fields.Datetime(string="เวลามอบหมาย")
    date_resolved = fields.Datetime(string="เวลาแก้ไข")
    resolution_time = fields.Float(string="เวลาแก้ไข (นาที)", compute="_compute_resolution_time", store=True)

    # Resolution
    resolution_note = fields.Text(string="บันทึกการแก้ไข")
    proof_image_ids = fields.Many2many(
        "ir.attachment", "patrol_incident_proof_rel", "incident_id", "attachment_id",
        string="ภาพยืนยันการแก้ไข",
    )

    @api.depends("severity")
    def _compute_priority(self):
        mapping = {"low": "0", "medium": "1", "high": "2", "critical": "3"}
        for rec in self:
            rec.priority = mapping.get(rec.severity, "0")

    @api.depends("date_reported", "date_resolved")
    def _compute_resolution_time(self):
        for rec in self:
            if rec.date_reported and rec.date_resolved:
                delta = rec.date_resolved - rec.date_reported
                rec.resolution_time = delta.total_seconds() / 60
            else:
                rec.resolution_time = 0

    def action_assign(self):
        self.write({"state": "assigned", "date_assigned": fields.Datetime.now()})

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_resolve(self):
        self.write({"state": "resolved", "date_resolved": fields.Datetime.now()})

    def action_close(self):
        self.write({"state": "closed"})

    def action_escalate(self):
        """Escalate ไปหน่วยเหนือตามสายบัญชาการ"""
        for rec in self:
            if rec.soldier_id and rec.soldier_id.unit_id:
                parent_unit = rec.soldier_id.unit_id.parent_id
                if parent_unit:
                    rec.escalated_to = parent_unit
                    rec.message_post(body=f"Escalated ไปยัง {parent_unit.name}")
