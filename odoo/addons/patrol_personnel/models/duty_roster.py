from odoo import models, fields, api


class DutyRoster(models.Model):
    _name = "patrol.duty.roster"
    _description = "ตารางเวรรักษาการ"
    _order = "date_start desc"

    name = fields.Char(string="ชื่อเวร", required=True)
    duty_type = fields.Selection(
        [
            ("guard", "ยาม/รักษาการ"),
            ("patrol", "ลาดตะเวน"),
            ("standby", "เตรียมพร้อม"),
            ("rest", "พัก"),
        ],
        string="ประเภท",
        default="guard",
        required=True,
    )
    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร", required=True)
    unit_id = fields.Many2one("patrol.unit", string="หน่วย")
    date_start = fields.Datetime(string="เริ่ม", required=True)
    date_end = fields.Datetime(string="สิ้นสุด", required=True)
    location = fields.Char(string="สถานที่")
    note = fields.Text(string="หมายเหตุ")
    state = fields.Selection(
        [("scheduled", "กำหนดแล้ว"), ("on_duty", "อยู่เวร"), ("completed", "เสร็จ"), ("absent", "ขาด")],
        string="สถานะ",
        default="scheduled",
    )
