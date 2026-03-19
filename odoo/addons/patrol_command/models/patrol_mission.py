from odoo import models, fields, api
from odoo.exceptions import UserError


class PatrolMission(models.Model):
    _name = "patrol.mission"
    _description = "ภารกิจ (Mission)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, code"

    name = fields.Char(string="ชื่อภารกิจ", required=True, tracking=True)
    code = fields.Char(string="รหัสภารกิจ", readonly=True, copy=False, default="New")
    mission_type = fields.Selection(
        [
            ("patrol", "ลาดตะเวน"),
            ("surveillance", "เฝ้าระวัง"),
            ("escort", "คุ้มกัน"),
            ("search", "ค้นหา"),
            ("other", "อื่นๆ"),
        ],
        string="ประเภท",
        default="patrol",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "ร่าง"),
            ("planned", "วางแผน"),
            ("active", "ปฏิบัติการ"),
            ("completed", "เสร็จสิ้น"),
            ("cancelled", "ยกเลิก"),
        ],
        string="สถานะ",
        default="draft",
        tracking=True,
    )
    color = fields.Integer(string="สี", help="สำหรับแยกสีบนแผนที่/dashboard")

    # Command
    commander_id = fields.Many2one("patrol.soldier", string="ผู้บังคับภารกิจ", tracking=True)
    unit_id = fields.Many2one("patrol.unit", string="หน่วยรับผิดชอบ")

    # Resources
    soldier_ids = fields.Many2many("patrol.soldier", string="กำลังพล")
    equipment_ids = fields.Many2many("patrol.equipment", string="อุปกรณ์")
    soldier_count = fields.Integer(compute="_compute_counts")
    equipment_count = fields.Integer(compute="_compute_counts")

    # Schedule
    date_start = fields.Datetime(string="เวลาเริ่ม")
    date_end = fields.Datetime(string="เวลาสิ้นสุด")

    # Area
    area_geojson = fields.Text(string="พื้นที่ปฏิบัติการ (GeoJSON)")
    route_geojson = fields.Text(string="เส้นทางลาดตะเวน (GeoJSON)")

    # Details
    description = fields.Html(string="รายละเอียด")

    # Related
    incident_ids = fields.One2many("patrol.incident", "mission_id", string="เหตุการณ์")
    gps_log_ids = fields.One2many("patrol.gps.log", "mission_id", string="GPS Tracks")
    incident_count = fields.Integer(compute="_compute_counts")

    @api.depends("soldier_ids", "equipment_ids", "incident_ids")
    def _compute_counts(self):
        for rec in self:
            rec.soldier_count = len(rec.soldier_ids)
            rec.equipment_count = len(rec.equipment_ids)
            rec.incident_count = len(rec.incident_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("patrol.mission") or "New"
        return super().create(vals_list)

    def action_plan(self):
        self.write({"state": "planned"})

    def action_activate(self):
        for rec in self:
            if not rec.soldier_ids:
                raise UserError("ต้องมอบหมายกำลังพลก่อนเริ่มภารกิจ")
            rec.state = "active"
            # Start all equipment streams
            rec.equipment_ids.filtered(lambda e: e.state == "ready").action_start_stream()

    def action_complete(self):
        for rec in self:
            rec.state = "completed"
            rec.equipment_ids.action_stop_stream()

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            rec.equipment_ids.action_stop_stream()
