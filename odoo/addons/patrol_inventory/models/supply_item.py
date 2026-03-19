from odoo import models, fields, api


class SupplyCategory(models.Model):
    _name = "patrol.supply.category"
    _description = "หมวดพัสดุ"

    name = fields.Char(string="ชื่อหมวด", required=True)
    code = fields.Char(string="รหัส")


class SupplyItem(models.Model):
    _name = "patrol.supply.item"
    _description = "พัสดุ / อุปกรณ์ในคลัง"
    _inherit = ["mail.thread"]
    _order = "category_id, name"

    name = fields.Char(string="ชื่อ", required=True)
    code = fields.Char(string="รหัส / Serial No.")
    category_id = fields.Many2one("patrol.supply.category", string="หมวด")
    item_type = fields.Selection(
        [
            ("weapon", "อาวุธ"),
            ("ammo", "กระสุน"),
            ("fuel", "เชื้อเพลิง"),
            ("food", "เสบียง"),
            ("medical", "เวชภัณฑ์"),
            ("spare_part", "อะไหล่"),
            ("comms", "อุปกรณ์สื่อสาร"),
            ("other", "อื่นๆ"),
        ],
        string="ประเภท",
        required=True,
    )
    unit_of_measure = fields.Char(string="หน่วยนับ", default="ชิ้น")
    quantity = fields.Float(string="จำนวนคงเหลือ", tracking=True)
    min_quantity = fields.Float(string="จำนวนขั้นต่ำ", help="แจ้งเตือนเมื่อต่ำกว่านี้")
    is_low_stock = fields.Boolean(compute="_compute_low_stock", store=True)
    location = fields.Char(string="ที่เก็บ")
    assigned_to = fields.Many2one("patrol.soldier", string="ผู้รับผิดชอบ")
    unit_id = fields.Many2one("patrol.unit", string="หน่วย")
    is_serialized = fields.Boolean(string="ติดตาม Serial", default=False)
    note = fields.Text(string="หมายเหตุ")

    @api.depends("quantity", "min_quantity")
    def _compute_low_stock(self):
        for rec in self:
            rec.is_low_stock = rec.min_quantity > 0 and rec.quantity <= rec.min_quantity
