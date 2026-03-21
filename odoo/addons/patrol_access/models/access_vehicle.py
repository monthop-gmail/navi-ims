from odoo import models, fields, api


class AccessVehicle(models.Model):
    _name = "patrol.access.vehicle"
    _description = "ทะเบียนยานพาหนะ / เรือ"
    _inherit = ["mail.thread"]
    _order = "plate_number"

    plate_number = fields.Char(string="ทะเบียน / หมายเลข", required=True, index=True,
                               help="ทะเบียนรถ หรือ หมายเลขเรือ / ชื่อเรือ")
    category = fields.Selection(
        [
            ("land", "ยานพาหนะทางบก"),
            ("vessel", "เรือ / ยานพาหนะทางน้ำ"),
        ],
        string="หมวด",
        default="land",
        required=True,
    )
    vehicle_type = fields.Selection(
        [
            # ทางบก
            ("military", "ยานพาหนะทหาร"),
            ("official", "รถราชการ"),
            ("staff", "รถเจ้าหน้าที่"),
            ("visitor", "รถผู้มาติดต่อ"),
            ("delivery", "รถขนส่ง"),
            # ทางน้ำ
            ("military_vessel", "เรือทหาร"),
            ("patrol_boat", "เรือลาดตะเวน"),
            ("fishing", "เรือประมง"),
            ("cargo_vessel", "เรือบรรทุก"),
            ("speedboat", "เรือเร็ว"),
            ("longtail", "เรือหางยาว"),
            ("ferry", "เรือข้ามฟาก"),
            ("visitor_vessel", "เรือผู้มาติดต่อ"),
            # ทั้งสอง
            ("blocked", "ต้องห้าม"),
        ],
        string="ประเภท",
        default="visitor",
        required=True,
        tracking=True,
    )
    brand = fields.Char(string="ยี่ห้อ/รุ่น")
    color = fields.Char(string="สี")
    photo = fields.Binary(string="รูปถ่าย", attachment=True)
    owner_id = fields.Many2one("patrol.access.person", string="เจ้าของ/ผู้ใช้")
    owner_name = fields.Char(string="ชื่อเจ้าของ (ถ้าไม่มีในระบบ)")

    # ─── Maritime fields (เรือ) ───
    vessel_name = fields.Char(string="ชื่อเรือ")
    hull_number = fields.Char(string="หมายเลขตัวเรือ")
    vessel_length = fields.Float(string="ความยาว (เมตร)")
    engine_count = fields.Integer(string="จำนวนเครื่องยนต์")
    flag = fields.Char(string="ธง / สัญชาติ")
    home_port = fields.Char(string="ท่าเรือประจำ")
    ais_mmsi = fields.Char(string="AIS MMSI", help="Maritime Mobile Service Identity สำหรับระบบ AIS")

    # Access rules
    access_level = fields.Selection(
        [("all", "ทุกจุด"), ("specific", "เฉพาะที่กำหนด"), ("none", "ไม่อนุญาต")],
        string="สิทธิ์เข้า-ออก",
        default="specific",
    )
    allowed_gate_ids = fields.Many2many("patrol.access.gate", string="จุดที่อนุญาต")
    valid_from = fields.Date(string="อนุญาตตั้งแต่")
    valid_until = fields.Date(string="อนุญาตถึง")

    note = fields.Text(string="หมายเหตุ")
    active = fields.Boolean(default=True)

    @api.onchange("category")
    def _onchange_category(self):
        if self.category == "vessel" and self.vehicle_type in ("military", "official", "staff", "visitor", "delivery"):
            self.vehicle_type = "visitor_vessel"
