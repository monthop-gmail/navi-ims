"""
Executive Dashboard API — KPI สำหรับผู้บริหาร
"""

from odoo import http, fields
from odoo.http import request
from datetime import timedelta
import json


class DashboardAPIController(http.Controller):

    @http.route("/patrol/api/dashboard/kpi", type="json", auth="user")
    def get_kpi(self):
        """KPI หลักสำหรับผู้บริหาร"""
        env = request.env
        now = fields.Datetime.now()
        today = fields.Date.today()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        Soldier = env["patrol.soldier"]
        Equipment = env["patrol.equipment"]
        Mission = env["patrol.mission"]
        Incident = env["patrol.incident"]

        # กำลังพล
        total_soldiers = Soldier.search_count([])
        online_soldiers = Soldier.search_count([("is_online", "=", True)])

        # ความพร้อมกำลังพล (ถ้ามี patrol_personnel)
        fit_count = total_soldiers
        if "readiness" in Soldier._fields:
            fit_count = Soldier.search_count([("readiness", "=", "fit")])

        # อุปกรณ์
        total_equip = Equipment.search_count([])
        ready_equip = Equipment.search_count([("state", "=", "ready")])
        active_equip = Equipment.search_count([("state", "=", "active")])
        maint_equip = Equipment.search_count([("state", "=", "maintenance")])

        # ภารกิจ
        active_missions = Mission.search_count([("state", "=", "active")])
        completed_month = Mission.search_count([("state", "=", "completed"), ("date_end", ">=", month_ago)])
        total_missions_month = Mission.search_count([("create_date", ">=", month_ago)])

        # เหตุการณ์
        active_incidents = Incident.search_count([("state", "not in", ["closed", "resolved"])])
        sos_active = Incident.search_count([("incident_type", "=", "sos"), ("state", "not in", ["closed", "resolved"])])
        incidents_today = Incident.search_count([("date_reported", ">=", fields.Datetime.to_string(now.replace(hour=0, minute=0, second=0)))])
        incidents_week = Incident.search_count([("date_reported", ">=", week_ago)])
        incidents_month = Incident.search_count([("date_reported", ">=", month_ago)])

        # เวลาตอบสนองเฉลี่ย (incident resolved)
        resolved = Incident.search([("state", "in", ["resolved", "closed"]), ("date_reported", ">=", month_ago)])
        avg_response = 0
        if resolved:
            total_time = sum(r.resolution_time for r in resolved if r.resolution_time)
            avg_response = total_time / len(resolved) if resolved else 0

        # ซ่อมบำรุง
        Maint = env.get("patrol.maintenance.request")
        pending_maint = 0
        maint_cost_month = 0
        if Maint:
            pending_maint = Maint.search_count([("state", "not in", ["verified", "cancelled"])])
            done_maint = Maint.search([("state", "=", "verified"), ("verified_date", ">=", month_ago)])
            maint_cost_month = sum(m.total_cost for m in done_maint)

        return {
            "personnel": {
                "total": total_soldiers,
                "online": online_soldiers,
                "fit": fit_count,
                "readiness_pct": round(fit_count / total_soldiers * 100) if total_soldiers else 0,
            },
            "equipment": {
                "total": total_equip,
                "ready": ready_equip,
                "active": active_equip,
                "maintenance": maint_equip,
                "readiness_pct": round((ready_equip + active_equip) / total_equip * 100) if total_equip else 0,
            },
            "missions": {
                "active": active_missions,
                "completed_month": completed_month,
                "total_month": total_missions_month,
                "success_rate": round(completed_month / total_missions_month * 100) if total_missions_month else 0,
            },
            "incidents": {
                "active": active_incidents,
                "sos_active": sos_active,
                "today": incidents_today,
                "week": incidents_week,
                "month": incidents_month,
                "avg_response_min": round(avg_response, 1),
            },
            "maintenance": {
                "pending": pending_maint,
                "cost_month": round(maint_cost_month, 2),
            },
        }

    @http.route("/patrol/api/dashboard/trends", type="json", auth="user")
    def get_trends(self, days=30):
        """แนวโน้ม incident รายวัน"""
        env = request.env
        now = fields.Datetime.now()
        days = int(days)

        result = []
        for i in range(days - 1, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0)
            day_end = day.replace(hour=23, minute=59, second=59)

            count = env["patrol.incident"].search_count([
                ("date_reported", ">=", fields.Datetime.to_string(day_start)),
                ("date_reported", "<=", fields.Datetime.to_string(day_end)),
            ])

            result.append({
                "date": day.strftime("%Y-%m-%d"),
                "label": day.strftime("%d/%m"),
                "incidents": count,
            })

        return result

    @http.route("/patrol/api/dashboard/incident_by_type", type="json", auth="user")
    def get_incident_by_type(self, days=30):
        """เหตุการณ์แยกตามประเภท"""
        env = request.env
        since = fields.Datetime.now() - timedelta(days=int(days))

        types = [("sos", "SOS"), ("ai_detection", "AI"), ("manual", "Manual"), ("geofence", "Geofence")]
        result = []
        for code, label in types:
            count = env["patrol.incident"].search_count([
                ("incident_type", "=", code),
                ("date_reported", ">=", since),
            ])
            result.append({"type": code, "label": label, "count": count})

        return result

    @http.route("/patrol/api/dashboard/incident_by_severity", type="json", auth="user")
    def get_incident_by_severity(self, days=30):
        """เหตุการณ์แยกตามความรุนแรง"""
        env = request.env
        since = fields.Datetime.now() - timedelta(days=int(days))

        severities = [("critical", "วิกฤต"), ("high", "สูง"), ("medium", "ปานกลาง"), ("low", "ต่ำ")]
        result = []
        for code, label in severities:
            count = env["patrol.incident"].search_count([
                ("severity", "=", code),
                ("date_reported", ">=", since),
            ])
            result.append({"severity": code, "label": label, "count": count})

        return result
