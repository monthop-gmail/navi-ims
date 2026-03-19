from odoo import models, fields


class PatrolGpsLog(models.Model):
    _name = "patrol.gps.log"
    _description = "บันทึก GPS"
    _order = "recorded_at desc"

    soldier_id = fields.Many2one("patrol.soldier", string="ทหาร", index=True, ondelete="cascade")
    equipment_id = fields.Many2one("patrol.equipment", string="อุปกรณ์", index=True, ondelete="cascade")
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจ", index=True, ondelete="set null")
    lat = fields.Float(string="ละติจูด", digits=(10, 8), required=True)
    lng = fields.Float(string="ลองจิจูด", digits=(10, 8), required=True)
    accuracy = fields.Float(string="ความแม่นยำ (m)")
    altitude = fields.Float(string="ความสูง (m)")
    speed = fields.Float(string="ความเร็ว (km/h)")
    recorded_at = fields.Datetime(string="เวลาบันทึก", required=True, index=True, default=fields.Datetime.now)

    def init(self):
        """Create composite indexes for GPS query performance"""
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS patrol_gps_log_soldier_time_idx
            ON patrol_gps_log (soldier_id, recorded_at DESC)
            WHERE soldier_id IS NOT NULL
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS patrol_gps_log_equipment_time_idx
            ON patrol_gps_log (equipment_id, recorded_at DESC)
            WHERE equipment_id IS NOT NULL
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS patrol_gps_log_mission_time_idx
            ON patrol_gps_log (mission_id, recorded_at DESC)
            WHERE mission_id IS NOT NULL
        """)
