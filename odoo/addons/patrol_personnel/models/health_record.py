from odoo import models, fields, api


class HealthRecord(models.Model):
    _name = "patrol.health.record"
    _description = "ประวัติสุขภาพ / ความพร้อม"
    _order = "check_date desc"

    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร", required=True, ondelete="cascade")
    check_date = fields.Date(string="วันที่ตรวจ", required=True, default=fields.Date.today)
    check_type = fields.Selection(
        [
            ("annual", "ตรวจประจำปี"),
            ("fitness", "ทดสอบสมรรถภาพ"),
            ("injury", "บาดเจ็บ"),
            ("illness", "เจ็บป่วย"),
            ("mental", "สุขภาพจิต"),
        ],
        string="ประเภท",
        default="annual",
    )
    readiness = fields.Selection(
        [
            ("fit", "พร้อมปฏิบัติงาน"),
            ("limited", "จำกัดการปฏิบัติ"),
            ("unfit", "ไม่พร้อม"),
        ],
        string="ความพร้อม",
        default="fit",
    )
    next_check_date = fields.Date(string="ตรวจครั้งถัดไป")
    description = fields.Text(string="รายละเอียด")
    confidential = fields.Boolean(string="ข้อมูลลับ", default=True)
