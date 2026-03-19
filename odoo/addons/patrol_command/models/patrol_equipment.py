from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PatrolEquipment(models.Model):
    _name = "patrol.equipment"
    _description = "อุปกรณ์ (Equipment)"
    _inherit = ["mail.thread"]
    _order = "equipment_type, name"

    name = fields.Char(string="ชื่ออุปกรณ์", required=True)
    equipment_type = fields.Selection(
        [
            ("fixed_camera", "กล้องคงที่"),
            ("drone", "โดรน"),
            ("body_camera", "กล้องติดตัว"),
        ],
        string="ประเภท",
        required=True,
        tracking=True,
    )
    protocol = fields.Selection(
        [
            ("rtsp", "RTSP"),
            ("rtmp", "RTMP"),
            ("webrtc", "WebRTC"),
            ("other", "อื่นๆ"),
        ],
        string="Protocol",
        default="rtsp",
    )
    stream_url = fields.Char(string="Stream URL", help="RTSP URL สำหรับกล้อง fixed เช่น rtsp://admin:pass@NVR_IP/...")
    stream_path = fields.Char(string="MediaMTX Path", help="เช่น fixed/cam-01, drone/drone-01")

    # Location
    gps_lat = fields.Float(string="ละติจูด", digits=(10, 8))
    gps_lng = fields.Float(string="ลองจิจูด", digits=(10, 8))

    # Status
    is_active = fields.Boolean(string="เปิดใช้งาน", default=True)
    is_streaming = fields.Boolean(string="กำลัง Stream", default=False)
    state = fields.Selection(
        [
            ("draft", "ร่าง"),
            ("ready", "พร้อม"),
            ("active", "ใช้งาน"),
            ("maintenance", "ซ่อมบำรุง"),
        ],
        string="สถานะ",
        default="draft",
        tracking=True,
    )

    # Config
    capture_interval = fields.Integer(string="ดึง Frame ทุก (ms)", default=2000)

    # Relations
    assigned_soldier_id = fields.Many2one("patrol.soldier", string="ทหารที่รับผิดชอบ")
    mission_ids = fields.Many2many("patrol.mission", string="ภารกิจ")

    active = fields.Boolean(default=True)

    def action_start_stream(self):
        """สั่ง Node.js เริ่มดึง frame จากกล้อง"""
        # TODO: เรียก HTTP API POST /api/camera/start
        for rec in self:
            rec.is_streaming = True
            rec.state = "active"
            _logger.info("START stream: %s → %s", rec.name, rec.stream_path)

    def action_stop_stream(self):
        """สั่ง Node.js หยุดดึง frame"""
        # TODO: เรียก HTTP API POST /api/camera/stop
        for rec in self:
            rec.is_streaming = False
            _logger.info("STOP stream: %s", rec.name)
