from odoo import models, fields


class ThreatZone(models.Model):
    _name = "patrol.threat.zone"
    _description = "พื้นที่เสี่ยง / จุดสนใจ"
    _order = "threat_level desc"

    name = fields.Char(string="ชื่อพื้นที่", required=True)
    zone_type = fields.Selection(
        [
            ("threat", "พื้นที่เสี่ยง"),
            ("interest", "จุดสนใจ"),
            ("safe", "พื้นที่ปลอดภัย"),
            ("restricted", "เขตหวงห้าม"),
        ],
        string="ประเภท",
        default="threat",
        required=True,
    )
    threat_level = fields.Selection(
        [("low", "ต่ำ"), ("medium", "ปานกลาง"), ("high", "สูง"), ("critical", "วิกฤต")],
        string="ระดับ",
        default="medium",
    )
    geojson = fields.Text(string="พื้นที่ (GeoJSON Polygon)", help="วาดบนแผนที่ Command Center")
    center_lat = fields.Float(string="จุดศูนย์กลาง lat", digits=(10, 8))
    center_lng = fields.Float(string="จุดศูนย์กลาง lng", digits=(10, 8))
    radius_m = fields.Float(string="รัศมี (เมตร)", help="ใช้แทน GeoJSON ถ้าเป็นวงกลม")
    description = fields.Html(string="รายละเอียด")
    valid_from = fields.Datetime(string="มีผลตั้งแต่")
    valid_until = fields.Datetime(string="มีผลถึง")
    active = fields.Boolean(default=True)
    color = fields.Char(string="สี (hex)", default="#ff0000")
