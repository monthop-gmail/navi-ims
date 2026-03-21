"""
Sighting API — AI รายงานทุกคน/รถที่เห็นจากกล้องในพื้นที่

Flow:
  1. Celery AI ตรวจจับคน/รถ จากกล้อง → POST /patrol/api/external/sighting
  2. ระบบ match กับ:
     - ทะเบียนบุคคล (patrol.access.person)
     - ทะเบียนรถ (patrol.access.vehicle)
     - Watchlist (patrol.watchlist) — ถ้าติดตั้ง patrol_intelligence
  3. บันทึก sighting + เช็คกฎแจ้งเตือน
  4. ถ้าตรง alert rule → สร้าง incident
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


class SightingAPIController(http.Controller):

    @http.route("/patrol/api/external/sighting", type="json", auth="none", csrf=False)
    def report_sighting(self, camera_name, sighting_type, plate_number=None,
                        person_match_id=None, confidence=0, snapshot_base64=None,
                        track_id=None, direction=None, bbox=None):
        """
        AI รายงานการพบเห็นคน/รถ

        Args:
            camera_name: ชื่อกล้อง (equipment.name)
            sighting_type: "person" / "vehicle"
            plate_number: ทะเบียน (ถ้าอ่านได้)
            person_match_id: patrol.access.person.id ที่ AI match ได้
            confidence: 0-100
            snapshot_base64: ภาพ base64
            track_id: tracking ID ข้ามกล้อง
            direction: entering/leaving/passing/stationary
            bbox: bounding box JSON
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)

        # หากล้อง
        equipment = env["patrol.equipment"].search([("name", "=", camera_name)], limit=1)
        if not equipment:
            return {"error": f"camera not found: {camera_name}"}

        import base64
        snapshot_binary = base64.b64decode(snapshot_base64) if snapshot_base64 else None

        # ─── Match person ───
        match_status = "unknown"
        person = None
        vehicle = None
        watchlist_entry = None

        if sighting_type == "person" and person_match_id:
            person = env["patrol.access.person"].browse(int(person_match_id))
            if person.exists():
                match_status = "known"
                if person.person_type == "blocked":
                    match_status = "watchlist"

        if sighting_type == "vehicle" and plate_number:
            vehicle = env["patrol.access.vehicle"].search([("plate_number", "=", plate_number)], limit=1)
            if vehicle:
                match_status = "known"
                if vehicle.vehicle_type == "blocked":
                    match_status = "watchlist"

        # ─── เช็ค watchlist (ถ้ามี patrol_intelligence) ───
        if "patrol.watchlist" in env:
            if sighting_type == "vehicle" and plate_number:
                wl = env["patrol.watchlist"].search([
                    ("entry_type", "=", "vehicle"),
                    ("plate_number", "=", plate_number),
                    ("status", "=", "active"),
                ], limit=1)
                if wl:
                    watchlist_entry = wl
                    match_status = "watchlist"

            if sighting_type == "person" and person and person.person_type == "blocked":
                wl = env["patrol.watchlist"].search([
                    ("entry_type", "=", "person"),
                    ("status", "=", "active"),
                ], limit=1)
                if wl:
                    watchlist_entry = wl

        # ─── สร้าง sighting record ───
        sighting = env["patrol.sighting"].create({
            "equipment_id": equipment.id,
            "sighting_type": sighting_type,
            "match_status": match_status,
            "person_id": person.id if person else False,
            "vehicle_id": vehicle.id if vehicle else False,
            "detected_plate": plate_number,
            "watchlist_id": watchlist_entry.id if watchlist_entry else False,
            "confidence": confidence,
            "snapshot": snapshot_binary,
            "track_id": track_id,
            "direction": direction,
            "bbox": bbox,
        })

        # ─── เช็ค alert rules ───
        incident_id = None
        alerts = env["patrol.sighting.alert"].search([("active", "=", True)])
        for alert in alerts:
            # เช็คว่ากล้องตรงไหม
            if alert.equipment_ids and equipment not in alert.equipment_ids:
                continue

            triggered = False
            if alert.alert_type == "watchlist" and match_status == "watchlist":
                triggered = True
            elif alert.alert_type == "unknown_person" and sighting_type == "person" and match_status == "unknown":
                triggered = True
            elif alert.alert_type == "unknown_vehicle" and sighting_type == "vehicle" and match_status == "unknown":
                triggered = True
            elif alert.alert_type == "blocked" and match_status == "watchlist":
                triggered = True
            elif alert.alert_type == "specific_person" and person and alert.person_id == person:
                triggered = True
            elif alert.alert_type == "specific_vehicle" and vehicle and alert.vehicle_id == vehicle:
                triggered = True

            if triggered and alert.create_incident:
                who = person.name if person else (plate_number or "ไม่รู้จัก")
                incident = env["patrol.incident"].create({
                    "name": f"[Sighting] {alert.name}: {who} ที่ {equipment.name}",
                    "incident_type": "ai_detection",
                    "severity": alert.severity,
                    "equipment_id": equipment.id,
                    "lat": equipment.gps_lat,
                    "lng": equipment.gps_lng,
                    "ai_type": f"sighting_{alert.alert_type}",
                    "ai_confidence": confidence / 100,
                })
                sighting.incident_id = incident.id
                incident_id = incident.id
                _logger.warning("SIGHTING ALERT: %s — %s at %s", alert.name, who, equipment.name)
                break  # 1 incident per sighting

        return {
            "status": "ok",
            "sighting_id": sighting.id,
            "match_status": match_status,
            "incident_id": incident_id,
            "track_id": track_id,
        }

    @http.route("/patrol/api/external/sighting_batch", type="json", auth="none", csrf=False)
    def report_sighting_batch(self, sightings):
        """Batch report — หลายการพบเห็นพร้อมกัน"""
        if not _check_api_key():
            return {"error": "unauthorized"}

        results = []
        for s in sightings:
            r = self.report_sighting(**s)
            results.append(r)

        return {"status": "ok", "count": len(results), "results": results}
