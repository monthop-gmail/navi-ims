from odoo import models, fields, api


class PatrolUnit(models.Model):
    _name = "patrol.unit"
    _description = "หน่วย (Unit)"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "unit_type, code"

    name = fields.Char(string="ชื่อหน่วย", required=True)
    code = fields.Char(string="รหัสหน่วย")
    unit_type = fields.Selection(
        [
            ("company", "กองร้อย"),
            ("platoon", "หมวด"),
            ("squad", "หมู่"),
            ("team", "ชุด"),
        ],
        string="ประเภทหน่วย",
        required=True,
        default="squad",
    )
    parent_id = fields.Many2one("patrol.unit", string="หน่วยเหนือ", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("patrol.unit", "parent_id", string="หน่วยรอง")
    commander_id = fields.Many2one("patrol.soldier", string="ผู้บังคับหน่วย")
    soldier_ids = fields.One2many("patrol.soldier", "unit_id", string="กำลังพล")
    soldier_count = fields.Integer(string="จำนวนกำลังพล", compute="_compute_soldier_count")
    active = fields.Boolean(default=True)

    @api.depends("soldier_ids")
    def _compute_soldier_count(self):
        for rec in self:
            rec.soldier_count = len(rec.soldier_ids)

    def name_get(self):
        result = []
        for rec in self:
            name = f"[{rec.code}] {rec.name}" if rec.code else rec.name
            result.append((rec.id, name))
        return result
