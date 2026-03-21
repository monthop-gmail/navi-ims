"""
Notification Channel — ส่งแจ้งเตือนจริง (LINE, Slack, Odoo)

ตั้งค่า channel ใน Odoo → Inngest worker เรียกใช้
"""

from odoo import models, fields, api
import logging
import requests

_logger = logging.getLogger(__name__)


class NotificationChannel(models.Model):
    _name = "patrol.notification.channel"
    _description = "ช่องทางแจ้งเตือน"

    name = fields.Char(string="ชื่อ", required=True)
    channel_type = fields.Selection(
        [
            ("line_notify", "LINE Notify"),
            ("line_oa", "LINE Official Account"),
            ("slack", "Slack Webhook"),
            ("discord", "Discord Webhook"),
            ("odoo", "Odoo Internal"),
        ],
        string="ประเภท",
        required=True,
    )
    token = fields.Char(string="Token / Webhook URL")
    is_active = fields.Boolean(string="เปิดใช้งาน", default=True)

    # กรอง
    min_severity = fields.Selection(
        [("low", "ทุกระดับ"), ("medium", "ปานกลางขึ้นไป"), ("high", "สูงขึ้นไป"), ("critical", "วิกฤตเท่านั้น")],
        string="ส่งเมื่อ severity",
        default="medium",
    )
    notify_sos = fields.Boolean(string="แจ้ง SOS", default=True)
    notify_incident = fields.Boolean(string="แจ้ง Incident", default=True)
    notify_mission = fields.Boolean(string="แจ้ง Mission", default=True)
    notify_geofence = fields.Boolean(string="แจ้ง Geofence", default=False)
    notify_access = fields.Boolean(string="แจ้ง Access (คำขอเข้า-ออก)", default=False)

    def send_notification(self, message, title=None, image_url=None):
        """ส่งแจ้งเตือนผ่าน channel นี้"""
        self.ensure_one()
        if not self.is_active or not self.token:
            return False

        try:
            if self.channel_type == "line_notify":
                return self._send_line_notify(message, image_url)
            elif self.channel_type == "slack":
                return self._send_slack(message, title)
            elif self.channel_type == "discord":
                return self._send_discord(message, title)
            elif self.channel_type == "odoo":
                return self._send_odoo(message, title)
        except Exception as e:
            _logger.error("Notification failed [%s]: %s", self.name, e)
            return False

    def _send_line_notify(self, message, image_url=None):
        """LINE Notify API"""
        data = {"message": f"\n{message}"}
        if image_url:
            data["imageThumbnail"] = image_url
            data["imageFullsize"] = image_url

        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {self.token}"},
            data=data,
            timeout=10,
        )
        _logger.info("LINE Notify [%s]: %s", self.name, resp.status_code)
        return resp.status_code == 200

    def _send_slack(self, message, title=None):
        """Slack Incoming Webhook"""
        payload = {"text": f"*{title or 'NAVI-IMS'}*\n{message}"}
        resp = requests.post(self.token, json=payload, timeout=10)
        return resp.status_code == 200

    def _send_discord(self, message, title=None):
        """Discord Webhook"""
        payload = {"content": f"**{title or 'NAVI-IMS'}**\n{message}"}
        resp = requests.post(self.token, json=payload, timeout=10)
        return resp.status_code == 204

    def _send_odoo(self, message, title=None):
        """Odoo internal notification (bus)"""
        self.env["bus.bus"]._sendone(
            "broadcast",
            "simple_notification",
            {"title": title or "NAVI-IMS", "message": message, "type": "warning"},
        )
        return True


class NotificationLog(models.Model):
    _name = "patrol.notification.log"
    _description = "ประวัติการแจ้งเตือน"
    _order = "sent_at desc"

    channel_id = fields.Many2one("patrol.notification.channel", string="ช่องทาง")
    channel_type = fields.Selection(related="channel_id.channel_type", store=True)
    message = fields.Text(string="ข้อความ")
    incident_id = fields.Many2one("patrol.incident", string="เหตุการณ์")
    mission_id = fields.Many2one("patrol.mission", string="ภารกิจ")
    sent_at = fields.Datetime(string="เวลาส่ง", default=fields.Datetime.now)
    success = fields.Boolean(string="สำเร็จ")
    error = fields.Text(string="Error (ถ้ามี)")
