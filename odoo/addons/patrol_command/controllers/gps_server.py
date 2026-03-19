"""
GPS Server Integration — รับ GPS จาก drone/อุปกรณ์ tracker

รองรับหลาย protocol:
  1. HTTP POST (ง่ายสุด — custom firmware push JSON)
  2. Traccar API (forward จาก Traccar server)
  3. OsmAnd protocol (?lat=xx&lon=xx&...)

ทุก protocol แปลงเป็น patrol.gps.log เหมือนกันหมด
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


class GpsServerController(http.Controller):

    # ─── Protocol 1: HTTP POST JSON (custom firmware) ───

    @http.route("/patrol/api/external/drone_gps", type="json", auth="none", csrf=False)
    def drone_gps_json(self, device_id, lat, lng, altitude=None, speed=None, heading=None, accuracy=None):
        """
        Drone GPS — HTTP POST JSON
        device_id = equipment.name ใน Odoo (เช่น "DRONE-01")
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        return self._process_device_gps(device_id, lat, lng, altitude, speed, accuracy)

    @http.route("/patrol/api/external/drone_gps_batch", type="json", auth="none", csrf=False)
    def drone_gps_batch(self, entries):
        """Batch GPS สำหรับ drone หลายตัว"""
        if not _check_api_key():
            return {"error": "unauthorized"}

        results = []
        for entry in entries:
            r = self._process_device_gps(
                entry.get("device_id"),
                entry.get("lat"),
                entry.get("lng"),
                entry.get("altitude"),
                entry.get("speed"),
                entry.get("accuracy"),
            )
            results.append(r)

        return {"status": "ok", "count": len(results), "results": results}

    # ─── Protocol 2: OsmAnd (GET with query params) ───
    # หลาย GPS tracker รองรับ OsmAnd protocol
    # URL: /patrol/gps/osmand?id=DRONE-01&lat=13.75&lon=100.50&altitude=100&speed=5

    @http.route("/patrol/gps/osmand", type="http", auth="none", csrf=False, methods=["GET"])
    def drone_gps_osmand(self, id=None, lat=None, lon=None, altitude=None, speed=None, **kw):
        """
        OsmAnd Protocol — GET request จาก GPS tracker
        ไม่ต้อง API key (tracker ส่ง URL ตรงๆ)
        ใช้ device_id match กับ equipment.name
        """
        if not id or not lat or not lon:
            return request.make_response("ERR: missing id/lat/lon", status=400)

        try:
            result = self._process_device_gps(
                str(id),
                float(lat),
                float(lon),
                float(altitude) if altitude else None,
                float(speed) if speed else None,
            )
            if result.get("error"):
                return request.make_response(f"ERR: {result['error']}", status=404)
            return request.make_response("OK", status=200)
        except Exception as e:
            _logger.error("OsmAnd GPS error: %s", e)
            return request.make_response(f"ERR: {e}", status=500)

    # ─── Protocol 3: Traccar API forward ───

    @http.route("/patrol/api/external/traccar_forward", type="json", auth="none", csrf=False)
    def traccar_forward(self, positions):
        """
        รับ position forward จาก Traccar server
        Traccar config: forward.url = http://odoo:8069/patrol/api/external/traccar_forward
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        results = []
        for pos in positions:
            device_name = pos.get("deviceId") or pos.get("uniqueId")
            r = self._process_device_gps(
                str(device_name),
                pos.get("latitude"),
                pos.get("longitude"),
                pos.get("altitude"),
                pos.get("speed"),
                pos.get("accuracy"),
            )
            results.append(r)

        return {"status": "ok", "count": len(results)}

    # ─── Core processing ───

    def _process_device_gps(self, device_id, lat, lng, altitude=None, speed=None, accuracy=None):
        """แปลง GPS จากทุก protocol เป็น patrol.gps.log"""
        env = request.env(su=True)

        equipment = env["patrol.equipment"].search([("name", "=", device_id)], limit=1)
        if not equipment:
            _logger.warning("GPS: unknown device %s", device_id)
            return {"device_id": device_id, "error": "device not found"}

        # หา mission
        mission_id = False
        if equipment.mission_ids:
            active = equipment.mission_ids.filtered(lambda m: m.state == "active")
            if active:
                mission_id = active[0].id

        # บันทึก GPS log
        env["patrol.gps.log"].create({
            "equipment_id": equipment.id,
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
            "altitude": altitude,
            "speed": speed,
            "accuracy": accuracy,
            "recorded_at": fields.Datetime.now(),
        })

        # อัพเดทตำแหน่งอุปกรณ์
        equipment.write({
            "gps_lat": lat,
            "gps_lng": lng,
        })

        return {"device_id": device_id, "status": "ok", "equipment_id": equipment.id}
