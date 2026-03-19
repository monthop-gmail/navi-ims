from odoo import models, fields, api


class PatrolSoldierPersonnel(models.Model):
    _inherit = "patrol.soldier"

    training_ids = fields.One2many("patrol.training", "soldier_id", string="ประวัติฝึก")
    training_count = fields.Integer(compute="_compute_personnel_counts")
    expired_training_count = fields.Integer(compute="_compute_personnel_counts")
    duty_ids = fields.One2many("patrol.duty.roster", "soldier_id", string="ตารางเวร")
    health_ids = fields.One2many("patrol.health.record", "soldier_id", string="ประวัติสุขภาพ")
    readiness = fields.Selection(
        [("fit", "พร้อม"), ("limited", "จำกัด"), ("unfit", "ไม่พร้อม")],
        string="ความพร้อม",
        compute="_compute_readiness",
        store=True,
    )

    @api.depends("training_ids", "training_ids.is_expired")
    def _compute_personnel_counts(self):
        for rec in self:
            rec.training_count = len(rec.training_ids)
            rec.expired_training_count = len(rec.training_ids.filtered("is_expired"))

    @api.depends("health_ids", "health_ids.readiness")
    def _compute_readiness(self):
        for rec in self:
            latest = rec.health_ids[:1]
            rec.readiness = latest.readiness if latest else "fit"
