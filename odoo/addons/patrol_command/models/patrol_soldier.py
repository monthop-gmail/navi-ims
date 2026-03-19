from odoo import models, fields, api


class PatrolSoldier(models.Model):
    _name = "patrol.soldier"
    _description = "กำลังพล (Soldier)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "callsign"

    name = fields.Char(string="ชื่อ-สกุล", required=True, tracking=True)
    callsign = fields.Char(string="สัญญาณเรียกขาน", required=True, index=True, copy=False)
    rank = fields.Selection(
        [
            ("pvt", "พลทหาร"),
            ("pfc", "สิบตรี"),
            ("cpl", "สิบโท"),
            ("sgt", "สิบเอก"),
            ("sms", "จ่าสิบเอก"),
            ("lt2", "ร้อยตรี"),
            ("lt1", "ร้อยโท"),
            ("cpt", "ร้อยเอก"),
            ("maj", "พันตรี"),
            ("ltc", "พันโท"),
            ("col", "พันเอก"),
        ],
        string="ยศ",
        default="pvt",
        tracking=True,
    )
    unit_id = fields.Many2one("patrol.unit", string="สังกัด", tracking=True)
    photo = fields.Binary(string="รูปถ่าย", attachment=True)
    phone = fields.Char(string="เบอร์โทร")

    # Real-time status (updated from Node.js / Socket.IO)
    is_online = fields.Boolean(string="ออนไลน์", default=False)
    stream_path = fields.Char(string="Stream Path")
    last_lat = fields.Float(string="ละติจูด", digits=(10, 8))
    last_lng = fields.Float(string="ลองจิจูด", digits=(10, 8))
    last_gps_time = fields.Datetime(string="GPS ล่าสุด")

    # Relations
    equipment_ids = fields.Many2many("patrol.equipment", string="อุปกรณ์")
    active_mission_id = fields.Many2one("patrol.mission", string="ภารกิจปัจจุบัน", compute="_compute_active_mission", store=True)
    mission_ids = fields.Many2many("patrol.mission", string="ประวัติภารกิจ")
    incident_ids = fields.One2many("patrol.incident", "soldier_id", string="เหตุการณ์")
    gps_log_ids = fields.One2many("patrol.gps.log", "soldier_id", string="GPS Logs")

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("callsign_unique", "UNIQUE(callsign)", "สัญญาณเรียกขานซ้ำ!"),
    ]

    @api.depends("mission_ids", "mission_ids.state")
    def _compute_active_mission(self):
        for rec in self:
            active = rec.mission_ids.filtered(lambda m: m.state == "active")
            rec.active_mission_id = active[:1].id if active else False

    def name_get(self):
        result = []
        for rec in self:
            rank_label = dict(self._fields["rank"].selection).get(rec.rank, "")
            result.append((rec.id, f"{rank_label} {rec.callsign} ({rec.name})"))
        return result
