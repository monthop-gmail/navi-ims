from odoo import models, fields


class Geofence(models.Model):
    _name = "patrol.geofence"
    _description = "เขตพื้นที่ (Geofence)"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(string="ชื่อเขต", required=True)
    fence_type = fields.Selection(
        [
            ("restricted", "เขตหวงห้าม"),
            ("safe", "เขตปลอดภัย"),
            ("operation", "เขตปฏิบัติการ"),
            ("alert", "เขตเฝ้าระวัง"),
        ],
        string="ประเภท",
        default="restricted",
        required=True,
    )
    trigger_on = fields.Selection(
        [
            ("enter", "เข้าเขต"),
            ("exit", "ออกจากเขต"),
            ("both", "ทั้งเข้าและออก"),
        ],
        string="แจ้งเตือนเมื่อ",
        default="enter",
    )
    severity = fields.Selection(
        [("low", "ต่ำ"), ("medium", "ปานกลาง"), ("high", "สูง"), ("critical", "วิกฤต")],
        string="ความรุนแรง",
        default="high",
    )
    auto_create_incident = fields.Boolean(string="สร้าง Incident อัตโนมัติ", default=True)

    # Geometry — circle or polygon
    geometry_type = fields.Selection(
        [("circle", "วงกลม"), ("polygon", "รูปหลายเหลี่ยม")],
        string="รูปแบบ",
        default="circle",
    )
    center_lat = fields.Float(string="จุดศูนย์กลาง lat", digits=(10, 8))
    center_lng = fields.Float(string="จุดศูนย์กลาง lng", digits=(10, 8))
    radius_m = fields.Float(string="รัศมี (เมตร)", default=500)
    geojson = fields.Text(string="GeoJSON Polygon", help="ใช้แทน circle ถ้าเป็น polygon")

    # Scope
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจ (ว่าง = ใช้ทุกภารกิจ)")
    applies_to = fields.Selection(
        [("all", "ทุกคน"), ("soldiers", "เฉพาะทหาร"), ("drones", "เฉพาะ drone"), ("equipment", "เฉพาะอุปกรณ์")],
        string="ใช้กับ",
        default="all",
    )

    color = fields.Char(string="สี (hex)", default="#ff0000")
    active = fields.Boolean(default=True)
    alert_ids = fields.One2many("patrol.geofence.alert", "geofence_id", string="ประวัติแจ้งเตือน")
    alert_count = fields.Integer(compute="_compute_alert_count")

    def _compute_alert_count(self):
        for rec in self:
            rec.alert_count = len(rec.alert_ids)
