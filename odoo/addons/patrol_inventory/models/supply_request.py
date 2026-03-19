from odoo import models, fields, api
from odoo.exceptions import UserError


class SupplyRequest(models.Model):
    _name = "patrol.supply.request"
    _description = "ใบเบิกพัสดุ"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc"

    name = fields.Char(string="เลขที่", readonly=True, copy=False, default="New")
    request_type = fields.Selection(
        [("issue", "เบิก"), ("return", "คืน"), ("transfer", "โอนย้าย")],
        string="ประเภท",
        default="issue",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "ร่าง"),
            ("submitted", "ส่งขออนุมัติ"),
            ("approved", "อนุมัติ"),
            ("done", "เบิกแล้ว"),
            ("rejected", "ไม่อนุมัติ"),
        ],
        string="สถานะ",
        default="draft",
        tracking=True,
    )
    requested_by = fields.Many2one("res.users", string="ผู้ขอ", default=lambda self: self.env.user)
    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร")
    unit_id = fields.Many2one("patrol.unit", string="หน่วย")
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจ")
    approved_by = fields.Many2one("res.users", string="ผู้อนุมัติ")
    request_date = fields.Datetime(string="วันที่ขอ", default=fields.Datetime.now)
    line_ids = fields.One2many("patrol.supply.request.line", "request_id", string="รายการ")
    note = fields.Text(string="หมายเหตุ")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("patrol.supply.request") or "New"
        return super().create(vals_list)

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_approve(self):
        self.write({"state": "approved", "approved_by": self.env.user.id})

    def action_done(self):
        """เบิกจริง — ลดจำนวนในคลัง"""
        for rec in self:
            for line in rec.line_ids:
                if line.item_id.quantity < line.quantity:
                    raise UserError(f"พัสดุ {line.item_id.name} ไม่พอ (เหลือ {line.item_id.quantity})")
                line.item_id.quantity -= line.quantity
            rec.state = "done"

    def action_reject(self):
        self.write({"state": "rejected"})


class SupplyRequestLine(models.Model):
    _name = "patrol.supply.request.line"
    _description = "รายการเบิก"

    request_id = fields.Many2one("patrol.supply.request", required=True, ondelete="cascade")
    item_id = fields.Many2one("patrol.supply.item", string="พัสดุ", required=True)
    quantity = fields.Float(string="จำนวน", default=1, required=True)
    available = fields.Float(string="คงเหลือ", related="item_id.quantity")
    note = fields.Char(string="หมายเหตุ")
