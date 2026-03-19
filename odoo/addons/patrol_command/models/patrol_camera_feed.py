from odoo import models, fields


class PatrolCameraFeed(models.Model):
    _name = "patrol.camera.feed"
    _description = "สถานะ Stream กล้อง"
    _order = "equipment_id"

    equipment_id = fields.Many2one("patrol.equipment", string="กล้อง", required=True, ondelete="cascade")
    stream_url = fields.Char(string="RTSP URL")
    hls_url = fields.Char(string="HLS URL", help="ดูผ่าน browser")
    whep_url = fields.Char(string="WHEP URL", help="WebRTC subscribe")
    is_live = fields.Boolean(string="กำลัง Stream")
    last_frame_at = fields.Datetime(string="Frame ล่าสุด")
    fps = fields.Float(string="FPS")
