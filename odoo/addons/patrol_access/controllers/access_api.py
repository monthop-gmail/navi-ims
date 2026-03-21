"""
Access Control API — AI ตรวจจับคน/รถ → ตัดสินใจเปิด/บล็อก/รออนุมัติ

Flow:
  1. AI ตรวจจับคน/รถ จากกล้อง → POST /patrol/api/external/access_check
  2. ระบบค้นหาในฐานข้อมูล:
     - รู้จัก + มีสิทธิ์ → เปิดประตูอัตโนมัติ
     - รู้จัก + ต้องห้าม → บล็อก + แจ้งเตือน
     - ไม่รู้จัก → สร้าง access request → รออนุมัติ
  3. บันทึก log ทุกกรณี
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


class AccessAPIController(http.Controller):

    @http.route("/patrol/api/external/access_check", type="json", auth="none", csrf=False)
    def access_check(self, gate_name, detection_type, plate_number=None,
                     face_match_id=None, confidence=0, snapshot_base64=None, direction="in"):
        """
        AI ตรวจจับคน/รถ แล้วส่งมาเช็ค

        Args:
            gate_name: ชื่อ gate (ตรงกับ patrol.access.gate.name)
            detection_type: "person" หรือ "vehicle"
            plate_number: ทะเบียนรถ (ถ้าเป็น vehicle)
            face_match_id: patrol.access.person.id ที่ AI match ได้ (ถ้ามี)
            confidence: ความมั่นใจ 0-100
            snapshot_base64: ภาพจากกล้อง (base64)
            direction: "in" หรือ "out"

        Returns:
            action: "open" / "block" / "pending" / "error"
        """
        if not _check_api_key():
            return {"error": "unauthorized"}

        env = request.env(su=True)

        # หา gate
        gate = env["patrol.access.gate"].search([("name", "=", gate_name)], limit=1)
        if not gate:
            return {"error": f"gate not found: {gate_name}", "action": "error"}

        import base64
        snapshot_binary = base64.b64decode(snapshot_base64) if snapshot_base64 else None

        # ─── Vehicle Detection ───
        if detection_type == "vehicle" and plate_number:
            return self._handle_vehicle(env, gate, plate_number, confidence, snapshot_binary, direction)

        # ─── Person Detection ───
        elif detection_type == "person":
            return self._handle_person(env, gate, face_match_id, confidence, snapshot_binary, direction)

        return {"error": "invalid detection_type", "action": "error"}

    def _handle_vehicle(self, env, gate, plate_number, confidence, snapshot, direction):
        """จัดการรถ"""
        vehicle = env["patrol.access.vehicle"].search([("plate_number", "=", plate_number)], limit=1)

        if vehicle and vehicle.vehicle_type == "blocked":
            # ─── บล็อก ───
            self._log(env, gate, direction, "vehicle", "blocked",
                      vehicle_id=vehicle.id, plate=plate_number, confidence=confidence, snapshot=snapshot)
            _logger.warning("ACCESS BLOCKED: vehicle %s at %s", plate_number, gate.name)
            return {"action": "block", "reason": "blacklisted", "plate": plate_number}

        elif vehicle and vehicle.access_level in ("all", "specific"):
            # ─── รู้จัก → เช็คสิทธิ์ ───
            allowed = vehicle.access_level == "all" or gate in vehicle.allowed_gate_ids
            if allowed and gate.auto_open_known:
                gate.action_open()
                self._log(env, gate, direction, "vehicle", "auto_granted",
                          vehicle_id=vehicle.id, plate=plate_number, confidence=confidence, snapshot=snapshot)
                return {"action": "open", "vehicle": vehicle.plate_number, "type": vehicle.vehicle_type}
            elif not allowed:
                self._log(env, gate, direction, "vehicle", "denied",
                          vehicle_id=vehicle.id, plate=plate_number, confidence=confidence, snapshot=snapshot)
                return {"action": "deny", "reason": "gate not allowed", "plate": plate_number}

        # ─── ไม่รู้จัก → สร้าง request ───
        if gate.require_approval_unknown:
            req = env["patrol.access.request"].create({
                "gate_id": gate.id,
                "request_type": "vehicle",
                "detected_plate": plate_number,
                "match_confidence": confidence,
                "snapshot_image": snapshot,
                "matched_vehicle_id": vehicle.id if vehicle else False,
            })
            self._log(env, gate, direction, "vehicle", "timeout",
                      plate=plate_number, confidence=confidence, snapshot=snapshot)
            _logger.info("ACCESS PENDING: vehicle %s at %s → request #%s", plate_number, gate.name, req.id)
            return {"action": "pending", "request_id": req.id, "plate": plate_number}

        return {"action": "deny", "reason": "unknown vehicle, no approval required"}

    def _handle_person(self, env, gate, face_match_id, confidence, snapshot, direction):
        """จัดการคน"""
        person = None
        if face_match_id:
            person = env["patrol.access.person"].browse(int(face_match_id))
            if not person.exists():
                person = None

        if person and person.person_type == "blocked":
            # ─── บล็อก ───
            self._log(env, gate, direction, "person", "blocked",
                      person_id=person.id, confidence=confidence, snapshot=snapshot)
            _logger.warning("ACCESS BLOCKED: person %s at %s", person.name, gate.name)
            return {"action": "block", "reason": "blacklisted", "person": person.name}

        elif person and person.is_active_access:
            # ─── รู้จัก + สิทธิ์ยังใช้ได้ ───
            allowed = person.access_level == "all" or gate in person.allowed_gate_ids
            if allowed and gate.auto_open_known and confidence >= 80:
                gate.action_open()
                self._log(env, gate, direction, "person", "auto_granted",
                          person_id=person.id, confidence=confidence, snapshot=snapshot)
                return {"action": "open", "person": person.name, "type": person.person_type}

        # ─── ไม่รู้จัก / ไม่มั่นใจพอ → สร้าง request ───
        if gate.require_approval_unknown:
            req = env["patrol.access.request"].create({
                "gate_id": gate.id,
                "request_type": "person",
                "match_confidence": confidence,
                "snapshot_image": snapshot,
                "matched_person_id": person.id if person else False,
            })
            self._log(env, gate, direction, "person", "timeout",
                      person_id=person.id if person else False, confidence=confidence, snapshot=snapshot)
            return {"action": "pending", "request_id": req.id}

        return {"action": "deny", "reason": "unknown person"}

    def _log(self, env, gate, direction, access_type, result,
             person_id=None, vehicle_id=None, plate=None, confidence=0, snapshot=None):
        """บันทึก access log"""
        env["patrol.access.log"].create({
            "gate_id": gate.id,
            "direction": direction,
            "access_type": access_type,
            "result": result,
            "person_id": person_id,
            "vehicle_id": vehicle_id,
            "detected_plate": plate,
            "match_confidence": confidence,
            "snapshot_image": snapshot,
        })
