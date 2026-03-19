"""
Equipment Maintenance — ระบบซ่อมบำรุงอุปกรณ์

ครบ loop: ตรวจพบ → แจ้งซ่อม → มอบหมาย → ซ่อม → ตรวจรับ → พร้อมใช้
+ Preventive maintenance (ซ่อมบำรุงตามกำหนด)
+ Corrective maintenance (ซ่อมเมื่อเสีย)
"""

from odoo import models, fields, api
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class MaintenanceRequest(models.Model):
    _name = "patrol.maintenance.request"
    _description = "ใบแจ้งซ่อม"
    _inherit = ["mail.thread", "mail.activity.mixin", "inngest.mixin"]
    _order = "priority desc, request_date desc"

    name = fields.Char(string="เรื่อง", required=True, tracking=True)
    code = fields.Char(string="เลขที่", readonly=True, copy=False, default="New")
    equipment_id = fields.Many2one("patrol.equipment", string="อุปกรณ์", required=True, tracking=True)
    equipment_type = fields.Selection(related="equipment_id.equipment_type", store=True)

    maintenance_type = fields.Selection(
        [
            ("corrective", "ซ่อมแก้ไข (เสีย)"),
            ("preventive", "ซ่อมบำรุงตามกำหนด"),
            ("inspection", "ตรวจสภาพ"),
        ],
        string="ประเภท",
        default="corrective",
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        [("0", "ปกติ"), ("1", "สำคัญ"), ("2", "เร่งด่วน"), ("3", "วิกฤต")],
        string="ความเร่งด่วน",
        default="0",
    )
    state = fields.Selection(
        [
            ("new", "แจ้งซ่อม"),
            ("assigned", "มอบหมายแล้ว"),
            ("in_progress", "กำลังซ่อม"),
            ("done", "ซ่อมเสร็จ"),
            ("verified", "ตรวจรับแล้ว"),
            ("cancelled", "ยกเลิก"),
        ],
        string="สถานะ",
        default="new",
        tracking=True,
    )

    # Who
    requested_by = fields.Many2one("res.users", string="ผู้แจ้ง", default=lambda self: self.env.user)
    technician_id = fields.Many2one("res.users", string="ช่างผู้รับผิดชอบ", tracking=True)
    verified_by = fields.Many2one("res.users", string="ผู้ตรวจรับ")

    # When
    request_date = fields.Datetime(string="วันที่แจ้ง", default=fields.Datetime.now, required=True)
    schedule_date = fields.Datetime(string="นัดซ่อม")
    start_date = fields.Datetime(string="เริ่มซ่อม")
    end_date = fields.Datetime(string="ซ่อมเสร็จ")
    verified_date = fields.Datetime(string="วันตรวจรับ")
    duration = fields.Float(string="เวลาซ่อม (ชม.)", compute="_compute_duration", store=True)

    # What
    description = fields.Html(string="อาการ/รายละเอียด")
    cause = fields.Text(string="สาเหตุ")
    resolution = fields.Text(string="วิธีแก้ไข")

    # Parts
    part_ids = fields.One2many("patrol.maintenance.part", "request_id", string="อะไหล่ที่ใช้")
    total_part_cost = fields.Float(string="ค่าอะไหล่รวม", compute="_compute_total_cost", store=True)
    labor_cost = fields.Float(string="ค่าแรง")
    total_cost = fields.Float(string="ค่าใช้จ่ายรวม", compute="_compute_total_cost", store=True)

    # Link
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจที่ได้รับผลกระทบ")

    @api.depends("start_date", "end_date")
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                delta = rec.end_date - rec.start_date
                rec.duration = delta.total_seconds() / 3600
            else:
                rec.duration = 0

    @api.depends("part_ids.cost", "labor_cost")
    def _compute_total_cost(self):
        for rec in self:
            rec.total_part_cost = sum(rec.part_ids.mapped("cost"))
            rec.total_cost = rec.total_part_cost + (rec.labor_cost or 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("patrol.maintenance.request") or "New"
        records = super().create(vals_list)
        # เปลี่ยนอุปกรณ์เป็นสถานะ maintenance
        for rec in records:
            if rec.maintenance_type == "corrective":
                rec.equipment_id.write({"state": "maintenance", "is_streaming": False})
        return records

    def action_assign(self):
        for rec in self:
            if not rec.technician_id:
                raise UserError("กรุณาเลือกช่างผู้รับผิดชอบก่อน")
            rec.state = "assigned"

    def action_start(self):
        self.write({"state": "in_progress", "start_date": fields.Datetime.now()})

    def action_done(self):
        self.write({"state": "done", "end_date": fields.Datetime.now()})

    def action_verify(self):
        for rec in self:
            rec.write({
                "state": "verified",
                "verified_by": self.env.user.id,
                "verified_date": fields.Datetime.now(),
            })
            # คืนอุปกรณ์เป็น ready
            rec.equipment_id.write({"state": "ready"})

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            if rec.equipment_id.state == "maintenance":
                rec.equipment_id.write({"state": "ready"})


class MaintenancePart(models.Model):
    _name = "patrol.maintenance.part"
    _description = "อะไหล่ที่ใช้ในการซ่อม"

    request_id = fields.Many2one("patrol.maintenance.request", string="ใบแจ้งซ่อม", required=True, ondelete="cascade")
    name = fields.Char(string="ชื่ออะไหล่", required=True)
    part_number = fields.Char(string="รหัสอะไหล่")
    quantity = fields.Float(string="จำนวน", default=1)
    unit_cost = fields.Float(string="ราคาต่อหน่วย")
    cost = fields.Float(string="รวม", compute="_compute_cost", store=True)
    note = fields.Char(string="หมายเหตุ")

    @api.depends("quantity", "unit_cost")
    def _compute_cost(self):
        for rec in self:
            rec.cost = rec.quantity * rec.unit_cost


class MaintenanceSchedule(models.Model):
    _name = "patrol.maintenance.schedule"
    _description = "แผนซ่อมบำรุงตามกำหนด"
    _order = "next_date"

    equipment_id = fields.Many2one("patrol.equipment", string="อุปกรณ์", required=True)
    name = fields.Char(string="รายการ", required=True, help="เช่น เปลี่ยนแบตเตอรี่, ทำความสะอาดเลนส์")
    interval_number = fields.Integer(string="ทุกๆ", default=30)
    interval_type = fields.Selection(
        [("day", "วัน"), ("week", "สัปดาห์"), ("month", "เดือน")],
        string="หน่วย",
        default="day",
    )
    last_done_date = fields.Date(string="ทำล่าสุด")
    next_date = fields.Date(string="ครั้งถัดไป", compute="_compute_next_date", store=True)
    active = fields.Boolean(default=True)

    @api.depends("last_done_date", "interval_number", "interval_type")
    def _compute_next_date(self):
        for rec in self:
            if rec.last_done_date and rec.interval_number:
                if rec.interval_type == "day":
                    rec.next_date = rec.last_done_date + relativedelta(days=rec.interval_number)
                elif rec.interval_type == "week":
                    rec.next_date = rec.last_done_date + relativedelta(weeks=rec.interval_number)
                elif rec.interval_type == "month":
                    rec.next_date = rec.last_done_date + relativedelta(months=rec.interval_number)
            else:
                rec.next_date = fields.Date.today()

    def action_create_request(self):
        """สร้างใบแจ้งซ่อมจากแผน preventive"""
        for rec in self:
            self.env["patrol.maintenance.request"].create({
                "name": f"[PM] {rec.name} — {rec.equipment_id.name}",
                "equipment_id": rec.equipment_id.id,
                "maintenance_type": "preventive",
            })
            rec.last_done_date = fields.Date.today()
