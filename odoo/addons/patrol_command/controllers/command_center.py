"""REST API สำหรับ Command Center Dashboard"""

from odoo import http
from odoo.http import request
import json


class CommandCenterController(http.Controller):

    @http.route("/patrol/api/soldiers", type="json", auth="user")
    def get_soldiers(self, mission_id=None):
        """ดึงข้อมูลทหารทั้งหมด (หรือเฉพาะภารกิจ)"""
        domain = []
        if mission_id:
            domain = [("mission_ids", "in", [int(mission_id)])]

        soldiers = request.env["patrol.soldier"].search_read(
            domain,
            ["callsign", "name", "rank", "unit_id", "is_online",
             "stream_path", "last_lat", "last_lng", "last_gps_time",
             "active_mission_id", "photo"],
        )
        return soldiers

    @http.route("/patrol/api/equipment", type="json", auth="user")
    def get_equipment(self, mission_id=None, equipment_type=None):
        """ดึงข้อมูลอุปกรณ์ (กล้อง/drone)"""
        domain = []
        if mission_id:
            domain.append(("mission_ids", "in", [int(mission_id)]))
        if equipment_type:
            domain.append(("equipment_type", "=", equipment_type))

        equipment = request.env["patrol.equipment"].search_read(
            domain,
            ["name", "equipment_type", "protocol", "stream_path",
             "gps_lat", "gps_lng", "is_streaming", "state",
             "assigned_soldier_id", "capture_interval"],
        )
        return equipment

    @http.route("/patrol/api/missions", type="json", auth="user")
    def get_missions(self, state=None):
        """ดึงข้อมูลภารกิจ"""
        domain = []
        if state:
            domain = [("state", "=", state)]

        missions = request.env["patrol.mission"].search_read(
            domain,
            ["code", "name", "mission_type", "state", "color",
             "commander_id", "date_start", "date_end",
             "soldier_count", "equipment_count", "incident_count",
             "area_geojson", "route_geojson"],
        )
        return missions

    @http.route("/patrol/api/incidents", type="json", auth="user")
    def get_incidents(self, mission_id=None, state=None):
        """ดึงเหตุการณ์"""
        domain = []
        if mission_id:
            domain.append(("mission_id", "=", int(mission_id)))
        if state:
            domain.append(("state", "=", state))

        incidents = request.env["patrol.incident"].search_read(
            domain,
            ["name", "incident_type", "severity", "state",
             "soldier_id", "lat", "lng", "date_reported",
             "assigned_to", "ai_type", "ai_confidence"],
            order="date_reported desc",
            limit=50,
        )
        return incidents

    @http.route("/patrol/api/gps_track", type="json", auth="user")
    def get_gps_track(self, soldier_id=None, equipment_id=None, mission_id=None, limit=500):
        """ดึง GPS track ย้อนหลัง"""
        domain = []
        if soldier_id:
            domain.append(("soldier_id", "=", int(soldier_id)))
        if equipment_id:
            domain.append(("equipment_id", "=", int(equipment_id)))
        if mission_id:
            domain.append(("mission_id", "=", int(mission_id)))

        logs = request.env["patrol.gps.log"].search_read(
            domain,
            ["soldier_id", "equipment_id", "lat", "lng",
             "accuracy", "altitude", "speed", "recorded_at"],
            order="recorded_at desc",
            limit=int(limit),
        )
        logs.reverse()
        return logs

    @http.route("/patrol/api/stats", type="json", auth="user")
    def get_stats(self, mission_id=None):
        """สรุปสถิติสำหรับ dashboard"""
        Soldier = request.env["patrol.soldier"]
        Incident = request.env["patrol.incident"]
        Mission = request.env["patrol.mission"]

        if mission_id:
            mission = Mission.browse(int(mission_id))
            soldiers = mission.soldier_ids
            online = soldiers.filtered("is_online")
            incidents = Incident.search([
                ("mission_id", "=", int(mission_id)),
                ("state", "not in", ["closed"]),
            ])
        else:
            soldiers = Soldier.search([])
            online = Soldier.search([("is_online", "=", True)])
            incidents = Incident.search([("state", "not in", ["closed"])])

        active_missions = Mission.search_count([("state", "=", "active")])
        sos_count = Incident.search_count([
            ("incident_type", "=", "sos"),
            ("state", "not in", ["resolved", "closed"]),
        ])

        return {
            "total_soldiers": len(soldiers),
            "online_soldiers": len(online),
            "active_incidents": len(incidents),
            "active_missions": active_missions,
            "active_sos": sos_count,
        }
