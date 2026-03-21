from odoo import models, fields


class AccessVehicle(models.Model):
    _name = "patrol.access.vehicle"
    _description = "ทะเบียนยานพาหนะ"
    _inherit = ["mail.thread"]
    _order = "plate_number"

    plate_number = fields.Char(string="ทะเบียนรถ", required=True, index=True)
    vehicle_type = fields.Selection(
        [
            ("military", "ยานพาหนะทหาร"),
            ("official", "รถราชการ"),
            ("staff", "รถเจ้าหน้าที่"),
            ("visitor", "รถผู้มาติดต่อ"),
            ("delivery", "รถขนส่ง"),
            ("blocked", "ยานพาหนะต้องห้าม"),
        ],
        string="ประเภท",
        default="visitor",
        required=True,
        tracking=True,
    )
    brand = fields.Char(string="ยี่ห้อ/รุ่น")
    color = fields.Char(string="สี")
    photo = fields.Binary(string="รูปถ่ายรถ", attachment=True)
    owner_id = fields.Many2one("patrol.access.person", string="เจ้าของ/ผู้ใช้")
    owner_name = fields.Char(string="ชื่อเจ้าของ (ถ้าไม่มีในระบบ)")

    # Access rules
    access_level = fields.Selection(
        [("all", "ทุกประตู"), ("specific", "เฉพาะที่กำหนด"), ("none", "ไม่อนุญาต")],
        string="สิทธิ์เข้า-ออก",
        default="specific",
    )
    allowed_gate_ids = fields.Many2many("patrol.access.gate", string="ประตูที่อนุญาต")
    valid_from = fields.Date(string="อนุญาตตั้งแต่")
    valid_until = fields.Date(string="อนุญาตถึง")

    note = fields.Text(string="หมายเหตุ")
    active = fields.Boolean(default=True)
