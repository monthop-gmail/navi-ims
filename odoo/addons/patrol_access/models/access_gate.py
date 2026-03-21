from odoo import models, fields
import logging
import requests

_logger = logging.getLogger(__name__)


class AccessGate(models.Model):
    _name = "patrol.access.gate"
    _description = "ประตู / ไม้กั้น / จุดเข้า-ออก"
    _inherit = ["mail.thread"]

    name = fields.Char(string="ชื่อประตู", required=True)
    gate_type = fields.Selection(
        [
            ("gate", "ประตู"),
            ("barrier", "ไม้กั้น"),
            ("boom", "แขนกั้น"),
            ("turnstile", "ประตูหมุน"),
        ],
        string="ประเภท",
        default="gate",
    )
    location = fields.Char(string="ตำแหน่ง")
    gps_lat = fields.Float(string="ละติจูด", digits=(10, 8))
    gps_lng = fields.Float(string="ลองจิจูด", digits=(10, 8))

    # Camera link
    camera_id = fields.Many2one("patrol.equipment", string="กล้องที่จุดนี้",
                                domain="[('equipment_type', '=', 'fixed_camera')]")

    # Control
    control_url = fields.Char(string="Control API URL", help="HTTP endpoint สำหรับสั่งเปิด/ปิด เช่น http://gate-controller:8080/api/open")
    control_method = fields.Selection(
        [("http_get", "HTTP GET"), ("http_post", "HTTP POST"), ("mqtt", "MQTT"), ("gpio", "GPIO")],
        string="วิธีสั่งเปิด",
        default="http_post",
    )
    is_open = fields.Boolean(string="สถานะ (เปิด/ปิด)", default=False)
    auto_close_seconds = fields.Integer(string="ปิดอัตโนมัติหลัง (วินาที)", default=10)

    # Policy
    auto_open_known = fields.Boolean(string="เปิดอัตโนมัติเมื่อรู้จัก", default=True)
    require_approval_unknown = fields.Boolean(string="ต้องอนุมัติเมื่อไม่รู้จัก", default=True)
    block_blacklist = fields.Boolean(string="บล็อกบุคคล/รถต้องห้ามทันที", default=True)

    active = fields.Boolean(default=True)

    def action_open(self):
        """สั่งเปิดประตู"""
        for rec in self:
            rec._send_gate_command("open")
            rec.is_open = True
            _logger.info("GATE OPEN: %s", rec.name)

    def action_close(self):
        """สั่งปิดประตู"""
        for rec in self:
            rec._send_gate_command("close")
            rec.is_open = False
            _logger.info("GATE CLOSE: %s", rec.name)

    def _send_gate_command(self, command):
        """ส่งคำสั่งไปที่ gate controller"""
        self.ensure_one()
        if not self.control_url:
            _logger.warning("Gate %s has no control URL", self.name)
            return

        try:
            if self.control_method == "http_get":
                requests.get(f"{self.control_url}/{command}", timeout=5)
            elif self.control_method == "http_post":
                requests.post(self.control_url, json={"command": command, "gate": self.name}, timeout=5)
            # TODO: mqtt, gpio
        except Exception as e:
            _logger.error("Gate command failed %s: %s", self.name, e)
