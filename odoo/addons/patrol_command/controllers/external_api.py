"""External API — รับข้อมูลจาก Node.js / Socket.IO
ใช้ API key authentication แทน session (เพราะ Node.js เรียก server-to-server)
"""

from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

# Simple API key — ใน production ควรเก็บใน ir.config_parameter
API_KEY_HEADER = "X-Patrol-Api-Key"


def _check_api_key():
    key = request.httprequest.headers.get(API_KEY_HEADER)
    expected = request.env["ir.config_parameter"].sudo().get_param("patrol.api_key", "patrol-secret-key")
    if key != expected:
        return False
    return True


class ExternalAPIController(http.Controller):

    @http.route("/patrol/api/external/gps", type="json", auth="none", csrf=False)
    def receive_gps(self, callsign, lat, lng, accuracy=None, altitude=None, speed=None, mission_code=None):
        """รับ GPS จาก Node.js (Socket.IO relay)"""
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)

        # หาทหารจาก callsign
        soldier = env["patrol.soldier"].search([("callsign", "=", callsign)], limit=1)
        if not soldier:
            return {"error": f"soldier not found: {callsign}"}

        # หา mission (ถ้าระบุ)
        mission_id = False
        if mission_code:
            mission = env["patrol.mission"].search([("code", "=", mission_code), ("state", "=", "active")], limit=1)
            mission_id = mission.id if mission else False
        elif soldier.active_mission_id:
            mission_id = soldier.active_mission_id.id

        # บันทึก GPS log
        env["patrol.gps.log"].create({
            "soldier_id": soldier.id,
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
            "accuracy": accuracy,
            "altitude": altitude,
            "speed": speed,
            "recorded_at": fields.Datetime.now(),
        })

        # อัพเดทตำแหน่งล่าสุดของทหาร
        soldier.write({
            "last_lat": lat,
            "last_lng": lng,
            "last_gps_time": fields.Datetime.now(),
        })

        return {"status": "ok", "soldier_id": soldier.id}

    @http.route("/patrol/api/external/gps_batch", type="json", auth="none", csrf=False)
    def receive_gps_batch(self, entries):
        """รับ GPS หลายรายการพร้อมกัน (ลด HTTP overhead)"""
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)
        results = []

        for entry in entries:
            callsign = entry.get("callsign")
            soldier = env["patrol.soldier"].search([("callsign", "=", callsign)], limit=1)
            if not soldier:
                results.append({"callsign": callsign, "error": "not found"})
                continue

            mission_id = soldier.active_mission_id.id if soldier.active_mission_id else False

            env["patrol.gps.log"].create({
                "soldier_id": soldier.id,
                "mission_id": mission_id,
                "lat": entry.get("lat"),
                "lng": entry.get("lng"),
                "accuracy": entry.get("accuracy"),
                "altitude": entry.get("altitude"),
                "speed": entry.get("speed"),
                "recorded_at": fields.Datetime.now(),
            })

            soldier.write({
                "last_lat": entry.get("lat"),
                "last_lng": entry.get("lng"),
                "last_gps_time": fields.Datetime.now(),
            })

            results.append({"callsign": callsign, "status": "ok"})

        return {"status": "ok", "count": len(results), "results": results}

    @http.route("/patrol/api/external/soldier_status", type="json", auth="none", csrf=False)
    def update_soldier_status(self, callsign, is_online, stream_path=None):
        """อัพเดทสถานะ online/offline ของทหาร"""
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)
        soldier = env["patrol.soldier"].search([("callsign", "=", callsign)], limit=1)
        if not soldier:
            return {"error": f"soldier not found: {callsign}"}

        vals = {"is_online": is_online}
        if stream_path is not None:
            vals["stream_path"] = stream_path

        soldier.write(vals)
        _logger.info("Soldier %s is now %s", callsign, "online" if is_online else "offline")

        return {"status": "ok", "soldier_id": soldier.id}

    @http.route("/patrol/api/external/sos", type="json", auth="none", csrf=False)
    def receive_sos(self, callsign, lat, lng):
        """รับ SOS จากทหาร → สร้าง Incident อัตโนมัติ"""
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)
        soldier = env["patrol.soldier"].search([("callsign", "=", callsign)], limit=1)
        if not soldier:
            return {"error": f"soldier not found: {callsign}"}

        mission_id = soldier.active_mission_id.id if soldier.active_mission_id else False

        incident = env["patrol.incident"].create({
            "name": f"SOS — {soldier.callsign} ({soldier.name})",
            "incident_type": "sos",
            "severity": "critical",
            "soldier_id": soldier.id,
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
        })

        _logger.warning("SOS from %s at %s,%s → incident #%s", callsign, lat, lng, incident.id)

        # TODO: ส่ง event ไป Inngest เพื่อเริ่ม workflow แจ้งเตือน

        return {"status": "ok", "incident_id": incident.id}
