from odoo import models, fields


class IntelReport(models.Model):
    _name = "patrol.intel.report"
    _description = "รายงานข่าวกรอง (INTSUM)"
    _inherit = ["mail.thread"]
    _order = "report_date desc"

    name = fields.Char(string="หัวข้อ", required=True)
    code = fields.Char(string="เลขที่", readonly=True, copy=False, default="New")
    report_type = fields.Selection(
        [
            ("intsum", "สรุปข่าวกรอง (INTSUM)"),
            ("spot", "รายงานด่วน (SPOT)"),
            ("patrol", "รายงานลาดตะเวน"),
            ("sigint", "ข่าวกรองสัญญาณ"),
            ("humint", "ข่าวกรองบุคคล"),
            ("other", "อื่นๆ"),
        ],
        string="ประเภท",
        default="intsum",
    )
    classification = fields.Selection(
        [("unclass", "ไม่ลับ"), ("confidential", "ลับ"), ("secret", "ลับมาก"), ("top_secret", "ลับที่สุด")],
        string="ชั้นความลับ",
        default="confidential",
    )
    report_date = fields.Datetime(string="วันที่รายงาน", default=fields.Datetime.now)
    reported_by = fields.Many2one("patrol.soldier", string="ผู้รายงาน")
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจ")
    content = fields.Html(string="เนื้อหา")
    lat = fields.Float(string="ละติจูด", digits=(10, 8))
    lng = fields.Float(string="ลองจิจูด", digits=(10, 8))
    watchlist_ids = fields.Many2many("patrol.watchlist", string="เกี่ยวกับ watchlist")
    attachment_ids = fields.Many2many("ir.attachment", string="ไฟล์แนบ")

    def _generate_code(self):
        return self.env["ir.sequence"].next_by_code("patrol.intel.report") or "New"

    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self._generate_code()
        return super().create(vals_list)
