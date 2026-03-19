"""
Geofence Check API — Node.js เรียกทุกครั้งที่ได้ GPS ใหม่
ตรวจว่าตำแหน่งอยู่ใน/นอก geofence หรือไม่
"""

import math
from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-Patrol-Api-Key"


def _check_api_key():
    key = request.httprequest.headers.get(API_KEY_HEADER)
    expected = request.env["ir.config_parameter"].sudo().get_param("patrol.api_key", "patrol-secret-key")
    return key == expected


def _haversine_distance(lat1, lng1, lat2, lng2):
    """คำนวณระยะห่าง 2 จุด (เมตร)"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class GeofenceCheckController(http.Controller):

    @http.route("/patrol/api/external/geofence_check", type="json", auth="none", csrf=False)
    def check_geofence(self, lat, lng, callsign=None, device_id=None):
        """
        ตรวจ GPS กับ geofence ทั้งหมด
        Node.js เรียกทุกครั้งที่ได้ GPS ใหม่ (หรือเรียกเป็น batch)
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)
        alerts = []

        # หา soldier / equipment
        soldier = None
        equipment = None
        if callsign:
            soldier = env["patrol.soldier"].search([("callsign", "=", callsign)], limit=1)
        if device_id:
            equipment = env["patrol.equipment"].search([("name", "=", device_id)], limit=1)

        # ดึง geofence ที่ active ทั้งหมด
        fences = env["patrol.geofence"].search([("active", "=", True)])

        for fence in fences:
            if fence.geometry_type == "circle":
                dist = _haversine_distance(lat, lng, fence.center_lat, fence.center_lng)
                is_inside = dist <= fence.radius_m
            else:
                # TODO: polygon check (point-in-polygon)
                continue

            # ตรวจว่าต้อง alert ไหม
            should_alert = False
            alert_type = None

            if fence.trigger_on in ("enter", "both") and is_inside:
                should_alert = True
                alert_type = "enter"
            elif fence.trigger_on in ("exit", "both") and not is_inside:
                # ต้องเช็คว่าเคยอยู่ข้างในก่อน (ดูจาก alert ล่าสุด)
                last_alert = env["patrol.geofence.alert"].search([
                    ("geofence_id", "=", fence.id),
                    ("soldier_id", "=", soldier.id if soldier else False),
                ], limit=1)
                if last_alert and last_alert.alert_type == "enter":
                    should_alert = True
                    alert_type = "exit"

            if not should_alert:
                continue

            # เช็คว่า alert ซ้ำไหม (ภายใน 5 นาที)
            recent = env["patrol.geofence.alert"].search([
                ("geofence_id", "=", fence.id),
                ("soldier_id", "=", soldier.id if soldier else False),
                ("alert_type", "=", alert_type),
                ("alert_time", ">=", fields.Datetime.subtract(fields.Datetime.now(), minutes=5)),
            ], limit=1)
            if recent:
                continue

            # สร้าง alert
            alert_vals = {
                "geofence_id": fence.id,
                "alert_type": alert_type,
                "soldier_id": soldier.id if soldier else False,
                "equipment_id": equipment.id if equipment else False,
                "lat": lat,
                "lng": lng,
            }

            # สร้าง incident อัตโนมัติ (ถ้าตั้งไว้)
            if fence.auto_create_incident:
                who = soldier.callsign if soldier else (equipment.name if equipment else "unknown")
                incident = env["patrol.incident"].create({
                    "name": f"[Geofence:{alert_type}] {who} — {fence.name}",
                    "incident_type": "geofence",
                    "severity": fence.severity,
                    "soldier_id": soldier.id if soldier else False,
                    "equipment_id": equipment.id if equipment else False,
                    "lat": lat,
                    "lng": lng,
                })
                alert_vals["incident_id"] = incident.id

            env["patrol.geofence.alert"].create(alert_vals)

            alerts.append({
                "geofence": fence.name,
                "type": alert_type,
                "severity": fence.severity,
            })

            _logger.warning(
                "GEOFENCE %s: %s %s fence '%s'",
                fence.severity.upper(),
                callsign or device_id or "unknown",
                alert_type,
                fence.name,
            )

        return {"status": "ok", "alerts": alerts, "alert_count": len(alerts)}
