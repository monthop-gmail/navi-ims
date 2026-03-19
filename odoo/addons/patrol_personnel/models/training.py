from odoo import models, fields, api


class TrainingCertificate(models.Model):
    _name = "patrol.training"
    _description = "ประวัติการฝึก / ใบรับรอง"
    _order = "expiry_date"

    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร", required=True, ondelete="cascade")
    name = fields.Char(string="หลักสูตร / ใบรับรอง", required=True)
    training_type = fields.Selection(
        [
            ("weapon", "อาวุธ"),
            ("first_aid", "ปฐมพยาบาล"),
            ("drone_pilot", "นักบิน drone"),
            ("comms", "สื่อสาร"),
            ("tactics", "ยุทธวิธี"),
            ("physical", "สมรรถภาพร่างกาย"),
            ("other", "อื่นๆ"),
        ],
        string="ประเภท",
        default="other",
    )
    date_completed = fields.Date(string="วันที่ผ่าน")
    expiry_date = fields.Date(string="วันหมดอายุ")
    is_expired = fields.Boolean(compute="_compute_expired", store=True)
    score = fields.Float(string="คะแนน")
    certificate_file = fields.Binary(string="ไฟล์ใบรับรอง", attachment=True)
    note = fields.Text(string="หมายเหตุ")

    @api.depends("expiry_date")
    def _compute_expired(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_expired = rec.expiry_date and rec.expiry_date < today


class TrainingRequirement(models.Model):
    _name = "patrol.training.requirement"
    _description = "หลักสูตรที่ต้องผ่าน (ตามยศ/ตำแหน่ง)"

    name = fields.Char(string="หลักสูตร", required=True)
    training_type = fields.Selection(
        related="", selection=[
            ("weapon", "อาวุธ"), ("first_aid", "ปฐมพยาบาล"),
            ("drone_pilot", "นักบิน drone"), ("comms", "สื่อสาร"),
            ("tactics", "ยุทธวิธี"), ("physical", "สมรรถภาพร่างกาย"),
            ("other", "อื่นๆ"),
        ],
        string="ประเภท",
    )
    required_for_rank = fields.Selection(
        related="", selection=[
            ("pvt", "พลทหาร"), ("sgt", "สิบเอก"), ("lt1", "ร้อยโท"), ("all", "ทุกยศ"),
        ],
        string="บังคับสำหรับยศ",
        default="all",
    )
    validity_months = fields.Integer(string="อายุใบรับรอง (เดือน)", default=12)
