from odoo import models, fields


class AccessPerson(models.Model):
    _name = "patrol.access.person"
    _description = "ทะเบียนบุคคล (Face Registry)"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(string="ชื่อ-สกุล", required=True)
    person_type = fields.Selection(
        [
            ("soldier", "ทหาร"),
            ("staff", "เจ้าหน้าที่"),
            ("visitor", "ผู้มาติดต่อ"),
            ("vip", "VIP"),
            ("contractor", "ผู้รับเหมา"),
            ("blocked", "บุคคลต้องห้าม"),
        ],
        string="ประเภท",
        default="visitor",
        required=True,
        tracking=True,
    )
    photo = fields.Binary(string="รูปถ่าย (สำหรับ Face Recognition)", attachment=True)
    photo_2 = fields.Binary(string="รูปถ่ายเพิ่มเติม", attachment=True)
    id_number = fields.Char(string="เลขบัตรประชาชน / บัตรทหาร")
    phone = fields.Char(string="เบอร์โทร")
    organization = fields.Char(string="หน่วยงาน / สังกัด")

    # Link to existing models
    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร (ถ้ามี)")

    # Access rules
    access_level = fields.Selection(
        [
            ("all", "ทุกประตู"),
            ("specific", "เฉพาะที่กำหนด"),
            ("none", "ไม่อนุญาต"),
        ],
        string="สิทธิ์เข้า-ออก",
        default="specific",
    )
    allowed_gate_ids = fields.Many2many("patrol.access.gate", string="ประตูที่อนุญาต")
    valid_from = fields.Date(string="อนุญาตตั้งแต่")
    valid_until = fields.Date(string="อนุญาตถึง")
    is_active_access = fields.Boolean(string="สิทธิ์ยังใช้ได้", compute="_compute_active", store=True)

    # AI
    face_encoding = fields.Text(string="Face Encoding (AI)", help="เก็บ face embedding สำหรับ matching")
    note = fields.Text(string="หมายเหตุ")
    active = fields.Boolean(default=True)

    def _compute_active(self):
        today = fields.Date.today()
        for rec in self:
            if rec.person_type == "blocked":
                rec.is_active_access = False
            elif rec.valid_from and rec.valid_until:
                rec.is_active_access = rec.valid_from <= today <= rec.valid_until
            elif rec.valid_until:
                rec.is_active_access = today <= rec.valid_until
            else:
                rec.is_active_access = True
