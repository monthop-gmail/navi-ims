from odoo import models, fields


class GeofenceAlert(models.Model):
    _name = "patrol.geofence.alert"
    _description = "ประวัติแจ้งเตือน Geofence"
    _order = "alert_time desc"

    geofence_id = fields.Many2one("patrol.geofence", string="เขต", required=True, ondelete="cascade")
    alert_type = fields.Selection([("enter", "เข้าเขต"), ("exit", "ออกจากเขต")], string="ประเภท", required=True)
    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร")
    equipment_id = fields.Many2one("patrol.equipment", string="อุปกรณ์")
    lat = fields.Float(string="ละติจูด", digits=(10, 8))
    lng = fields.Float(string="ลองจิจูด", digits=(10, 8))
    alert_time = fields.Datetime(string="เวลา", default=fields.Datetime.now)
    incident_id = fields.Many2one("patrol.incident", string="Incident ที่สร้าง")
    acknowledged = fields.Boolean(string="รับทราบแล้ว", default=False)
