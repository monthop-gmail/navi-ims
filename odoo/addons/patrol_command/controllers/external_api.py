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
        # Inngest event ส่งอัตโนมัติจาก create() override ใน patrol.incident

        return {"status": "ok", "incident_id": incident.id}

    @http.route("/patrol/api/external/ai_incident", type="json", auth="none", csrf=False)
    def receive_ai_incident(self, camera_name, anomaly_type, confidence, image_path=None, bbox=None):
        """
        AI ตรวจจับความผิดปกติ → สร้าง Incident อัตโนมัติ
        ใช้กับทุกกล้อง: fixed / body cam / drone
        Inngest workflow จะ trigger อัตโนมัติจาก create()
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)

        # หาอุปกรณ์จากชื่อ
        equipment = env["patrol.equipment"].search([("name", "=", camera_name)], limit=1)

        # หา mission ที่เกี่ยวข้อง (ถ้ามี)
        mission_id = False
        soldier_id = False
        lat = equipment.gps_lat if equipment else 0
        lng = equipment.gps_lng if equipment else 0

        if equipment:
            # ถ้าเป็น body cam → หาทหาร + mission
            if equipment.assigned_soldier_id:
                soldier_id = equipment.assigned_soldier_id.id
                lat = equipment.assigned_soldier_id.last_lat or lat
                lng = equipment.assigned_soldier_id.last_lng or lng
                if equipment.assigned_soldier_id.active_mission_id:
                    mission_id = equipment.assigned_soldier_id.active_mission_id.id

            # ถ้าเป็น drone/fixed → หา mission จาก equipment
            if not mission_id and equipment.mission_ids:
                active_missions = equipment.mission_ids.filtered(lambda m: m.state == "active")
                if active_missions:
                    mission_id = active_missions[0].id

        # กำหนด severity ตาม confidence
        if confidence >= 0.95:
            severity = "critical"
        elif confidence >= 0.85:
            severity = "high"
        elif confidence >= 0.7:
            severity = "medium"
        else:
            severity = "low"

        incident = env["patrol.incident"].create({
            "name": f"[AI:{anomaly_type}] {camera_name} ({confidence:.0%})",
            "incident_type": "ai_detection",
            "severity": severity,
            "equipment_id": equipment.id if equipment else False,
            "soldier_id": soldier_id,
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
            "ai_type": anomaly_type,
            "ai_confidence": confidence,
        })

        _logger.info(
            "AI incident: %s detected %s (%.0f%%) → incident #%s",
            camera_name, anomaly_type, confidence * 100, incident.id,
        )

        return {"status": "ok", "incident_id": incident.id, "severity": severity}
