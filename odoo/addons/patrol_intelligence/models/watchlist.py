from odoo import models, fields


class WatchlistEntry(models.Model):
    _name = "patrol.watchlist"
    _description = "บุคคล/ยานพาหนะที่ต้องจับตา"
    _inherit = ["mail.thread"]
    _order = "threat_level desc, name"

    name = fields.Char(string="ชื่อ / นามแฝง", required=True)
    entry_type = fields.Selection(
        [
            ("person", "บุคคล"),
            ("vehicle", "ยานพาหนะ"),
            ("vessel", "เรือ"),
            ("organization", "กลุ่ม/องค์กร"),
        ],
        string="ประเภท",
        required=True,
        default="person",
    )
    threat_level = fields.Selection(
        [("low", "ต่ำ"), ("medium", "ปานกลาง"), ("high", "สูง"), ("critical", "อันตราย")],
        string="ระดับภัยคุกคาม",
        default="medium",
        tracking=True,
    )
    status = fields.Selection(
        [("active", "เฝ้าระวัง"), ("captured", "จับกุมแล้ว"), ("cleared", "ปลอดภัย"), ("archived", "เก็บถาวร")],
        string="สถานะ",
        default="active",
        tracking=True,
    )

    # Person
    photo = fields.Binary(string="รูปถ่าย", attachment=True)
    alias = fields.Char(string="ชื่ออื่น / นามแฝง")
    id_number = fields.Char(string="เลขบัตร / หมายเลข")
    description = fields.Text(string="รูปพรรณ/รายละเอียด")

    # Vehicle
    plate_number = fields.Char(string="ทะเบียนรถ")
    vehicle_type = fields.Char(string="ประเภท/ยี่ห้อ/สี")

    # Intel
    last_seen_lat = fields.Float(string="พบล่าสุด lat", digits=(10, 8))
    last_seen_lng = fields.Float(string="พบล่าสุด lng", digits=(10, 8))
    last_seen_date = fields.Datetime(string="พบล่าสุดเมื่อ")
    last_seen_location = fields.Char(string="สถานที่พบล่าสุด")

    # Links
    incident_ids = fields.Many2many("patrol.incident", string="เหตุการณ์ที่เกี่ยวข้อง")
    note = fields.Html(string="บันทึก")
    active = fields.Boolean(default=True)
