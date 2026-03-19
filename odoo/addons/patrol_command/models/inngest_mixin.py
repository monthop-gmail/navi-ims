"""
Inngest Event Mixin — ส่ง event ไป Inngest Server จาก Odoo
ใช้ร่วมกันได้ทุก module
"""

import json
import logging
import requests
from odoo import models, api

_logger = logging.getLogger(__name__)


class InngestMixin(models.AbstractModel):
    _name = "inngest.mixin"
    _description = "Inngest Event Mixin"

    def _get_inngest_url(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "inngest.event_url", "http://inngest:8288"
        )

    def _get_inngest_event_key(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "inngest.event_key", "abc123def456"
        )

    def _send_inngest_event(self, event_name, data):
        """ส่ง event ไป Inngest Server"""
        url = self._get_inngest_url()
        key = self._get_inngest_event_key()

        try:
            resp = requests.post(
                f"{url}/e/{key}",
                json={"name": event_name, "data": data},
                timeout=5,
            )
            _logger.info("Inngest event sent: %s → %s", event_name, resp.status_code)
        except Exception as e:
            _logger.warning("Inngest event failed: %s — %s", event_name, e)
