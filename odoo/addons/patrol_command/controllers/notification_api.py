"""
Notification API — Inngest worker เรียกเพื่อส่งแจ้งเตือนจริง
"""

from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-Patrol-Api-Key"


def _check_api_key():
    key = request.httprequest.headers.get(API_KEY_HEADER)
    expected = request.env["ir.config_parameter"].sudo().get_param("patrol.api_key", "patrol-secret-key")
    return key == expected


class NotificationAPIController(http.Controller):

    @http.route("/patrol/api/external/notify", type="json", auth="none", csrf=False)
    def send_notification(self, message, severity="medium", title=None,
                          incident_id=None, mission_id=None, event_type="incident"):
        """
        Inngest worker เรียกเพื่อส่งแจ้งเตือนไปทุก channel ที่ตั้งไว้

        Args:
            message: ข้อความ
            severity: low/medium/high/critical
            title: หัวเรื่อง (optional)
            incident_id: patrol.incident.id (optional)
            mission_id: patrol.mission.id (optional)
            event_type: incident/sos/mission/geofence/access
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)

        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current_level = severity_order.get(severity, 1)

        channels = env["patrol.notification.channel"].search([("is_active", "=", True)])
        sent = 0
        failed = 0

        for ch in channels:
            # เช็ค severity
            min_level = severity_order.get(ch.min_severity, 0)
            if current_level < min_level:
                continue

            # เช็ค event type
            should_send = False
            if event_type == "sos" and ch.notify_sos:
                should_send = True
            elif event_type == "incident" and ch.notify_incident:
                should_send = True
            elif event_type == "mission" and ch.notify_mission:
                should_send = True
            elif event_type == "geofence" and ch.notify_geofence:
                should_send = True
            elif event_type == "access" and ch.notify_access:
                should_send = True

            if not should_send:
                continue

            # ส่ง
            try:
                success = ch.send_notification(message, title=title)
                env["patrol.notification.log"].create({
                    "channel_id": ch.id,
                    "message": message,
                    "incident_id": incident_id,
                    "mission_id": mission_id,
                    "success": success,
                })
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                env["patrol.notification.log"].create({
                    "channel_id": ch.id,
                    "message": message,
                    "success": False,
                    "error": str(e),
                })
                failed += 1

        _logger.info("Notifications sent: %d success, %d failed", sent, failed)
        return {"status": "ok", "sent": sent, "failed": failed}
