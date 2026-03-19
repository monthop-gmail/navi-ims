"""
Inngest Worker — Shared Workflow Engine สำหรับทุก module ใน NAVI-CC

Workflows:
  ① incident_lifecycle — จัดการเหตุการณ์จากทุกแหล่ง (AI/SOS/manual)
  ② mission_lifecycle  — จัดการภารกิจ (patrol + drone + อื่นๆ)
  ③ notification_send  — ส่งแจ้งเตือนแบบ generic (LINE/Slack/SMS)
"""

import os
import inngest
import inngest.fast_api
from fastapi import FastAPI
import httpx

# ─── Config ───

ODOO_URL = os.environ.get("ODOO_URL", "http://odoo:8069")
PATROL_API_KEY = os.environ.get("PATROL_API_KEY", "patrol-secret-key")
NODE_SERVICE_URL = os.environ.get("NODE_SERVICE_URL", "http://node-service:3000")

inngest_client = inngest.Inngest(
    app_id="navi-cc",
    event_key=os.environ.get("INNGEST_EVENT_KEY"),
    is_production=os.environ.get("INNGEST_DEV", "0") == "0",
)

# ─── Odoo Helpers ───

async def odoo_rpc(model: str, method: str, args: list, kwargs: dict = None):
    """เรียก Odoo JSON-RPC"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ODOO_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": ["odoo", 2, "admin", model, method, args, kwargs or {}],
                },
            },
            timeout=30,
        )
        data = resp.json()
        if data.get("error"):
            raise Exception(f"Odoo RPC error: {data['error']}")
        return data.get("result")


async def odoo_patrol_api(endpoint: str, params: dict):
    """เรียก Odoo Patrol External API"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ODOO_URL}{endpoint}",
            json={"jsonrpc": "2.0", "method": "call", "params": params},
            headers={"X-Patrol-Api-Key": PATROL_API_KEY},
            timeout=30,
        )
        data = resp.json()
        return data.get("result")


async def send_notification(channel: str, message: str, **extra):
    """
    ส่งแจ้งเตือน — placeholder สำหรับ LINE/Slack/SMS
    channel: "line" / "slack" / "sms" / "all"
    """
    print(f"[NOTIFY:{channel}] {message} | extra={extra}")
    # TODO: implement real notification
    #   LINE Notify: httpx.post("https://notify-api.line.me/api/notify", ...)
    #   Slack: httpx.post(SLACK_WEBHOOK_URL, ...)
    return {"sent": True, "channel": channel}


# ─── Helper: หา commander ตาม chain of command ───

async def find_commander(incident_data: dict) -> dict:
    """
    หาผู้บังคับบัญชาที่ต้องแจ้ง
    - ถ้ามี mission → ผบ.ภารกิจ
    - ถ้ามี soldier → ผบ.หน่วยของทหาร
    - fallback → ผบ.หน่วยที่ดูแลอุปกรณ์
    """
    mission_id = incident_data.get("mission_id")
    soldier_id = incident_data.get("soldier_id")

    if mission_id:
        missions = await odoo_rpc("patrol.mission", "read", [[mission_id], ["commander_id", "unit_id"]])
        if missions and missions[0].get("commander_id"):
            cmd = missions[0]["commander_id"]
            return {"id": cmd[0], "name": cmd[1], "source": "mission_commander"}

    if soldier_id:
        soldiers = await odoo_rpc("patrol.soldier", "read", [[soldier_id], ["unit_id"]])
        if soldiers and soldiers[0].get("unit_id"):
            unit_id = soldiers[0]["unit_id"][0]
            units = await odoo_rpc("patrol.unit", "read", [[unit_id], ["commander_id", "parent_id"]])
            if units and units[0].get("commander_id"):
                cmd = units[0]["commander_id"]
                return {"id": cmd[0], "name": cmd[1], "source": "unit_commander", "unit_id": unit_id}

    return {"id": None, "name": "ไม่พบผู้รับผิดชอบ", "source": "none"}


async def find_escalation_target(current_unit_id: int) -> dict:
    """หาหน่วยเหนือสำหรับ escalate"""
    if not current_unit_id:
        return {"id": None, "name": "ไม่มีหน่วยเหนือ"}

    units = await odoo_rpc("patrol.unit", "read", [[current_unit_id], ["parent_id"]])
    if units and units[0].get("parent_id"):
        parent_id = units[0]["parent_id"][0]
        parent_units = await odoo_rpc("patrol.unit", "read", [[parent_id], ["commander_id", "name"]])
        if parent_units and parent_units[0].get("commander_id"):
            cmd = parent_units[0]["commander_id"]
            return {"id": cmd[0], "name": cmd[1], "unit_id": parent_id, "unit_name": parent_units[0]["name"]}

    return {"id": None, "name": "ไม่มีหน่วยเหนือ"}


# ═══════════════════════════════════════════════════════
#  ① INCIDENT LIFECYCLE — Generic สำหรับทุกแหล่ง
# ═══════════════════════════════════════════════════════

@inngest_client.create_function(
    fn_id="incident-lifecycle",
    trigger=inngest.TriggerEvent(event="incident.created"),
)
async def incident_lifecycle(ctx: inngest.Context, step: inngest.Step):
    """
    จัดการเหตุการณ์ตั้งแต่สร้างจนปิด — ใช้กับทุก source:
    - AI ตรวจจับ (กล้อง fixed / body cam / drone)
    - ทหารกด SOS
    - รายงานด้วยตนเอง
    """
    event = ctx.event
    d = event.data

    incident_id = d.get("incident_id")
    incident_type = d.get("incident_type", "manual")   # sos / ai_detection / manual / geofence
    severity = d.get("severity", "medium")
    source = d.get("source", "unknown")                 # patrol / drone / fixed_camera / manual
    soldier_id = d.get("soldier_id")
    equipment_id = d.get("equipment_id")
    mission_id = d.get("mission_id")
    lat = d.get("lat")
    lng = d.get("lng")
    description = d.get("description", "")

    # ── Step 1: หา commander ที่ต้องแจ้ง ──
    commander = await step.run("find-commander", lambda: find_commander(d))

    # ── Step 2: แจ้งเตือนทันที ──
    severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🔴", "critical": "🚨"}
    emoji = severity_emoji.get(severity, "⚠️")

    notify_msg = (
        f"{emoji} เหตุการณ์ #{incident_id}\n"
        f"ประเภท: {incident_type} ({source})\n"
        f"ความรุนแรง: {severity}\n"
    )
    if description:
        notify_msg += f"รายละเอียด: {description}\n"
    if lat and lng:
        notify_msg += f"ตำแหน่ง: {lat:.6f}, {lng:.6f}\n"
    if commander.get("name"):
        notify_msg += f"แจ้ง: {commander['name']}"

    await step.run("notify-commander", lambda: send_notification(
        "all", notify_msg, incident_id=incident_id, commander=commander,
    ))

    # ── Step 3: อัพเดท incident state → assigned ──
    if commander.get("id"):
        await step.run("assign-commander", lambda: odoo_rpc(
            "patrol.incident", "write",
            [[incident_id], {
                "assigned_to": commander["id"],
                "state": "assigned",
            }],
        ))

    # ── Step 4: รอคนรับงาน ──
    timeout_accept = "15m" if severity == "critical" else "30m"

    accepted = await step.wait_for_event(
        "wait-accept",
        event="incident.accepted",
        if_exp=f"async.data.incident_id == {incident_id}",
        timeout=timeout_accept,
    )

    if not accepted:
        # ── Escalate ไปหน่วยเหนือ ──
        unit_id = commander.get("unit_id")
        escalation = await step.run("find-escalation", lambda: find_escalation_target(unit_id))

        await step.run("notify-escalation", lambda: send_notification(
            "all",
            f"🔺 ESCALATE: เหตุการณ์ #{incident_id} ไม่มีคนรับงานใน {timeout_accept}\n"
            f"Escalate ไป: {escalation.get('unit_name', 'N/A')} — {escalation.get('name', 'N/A')}",
            incident_id=incident_id,
        ))

        if escalation.get("id"):
            await step.run("update-escalation", lambda: odoo_rpc(
                "patrol.incident", "write",
                [[incident_id], {
                    "escalated_to": escalation.get("unit_id"),
                    "assigned_to": escalation["id"],
                }],
            ))

        # รอรอบ 2
        accepted = await step.wait_for_event(
            "wait-accept-escalated",
            event="incident.accepted",
            if_exp=f"async.data.incident_id == {incident_id}",
            timeout="2h",
        )

        if not accepted:
            await step.run("notify-timeout", lambda: send_notification(
                "all",
                f"❌ TIMEOUT: เหตุการณ์ #{incident_id} ไม่มีคนรับงานหลัง escalate",
                incident_id=incident_id,
            ))
            return {"status": "timeout", "incident_id": incident_id}

    # ── Step 5: อัพเดท state → in_progress ──
    await step.run("mark-in-progress", lambda: odoo_rpc(
        "patrol.incident", "write",
        [[incident_id], {"state": "in_progress"}],
    ))

    # ── Step 6: รอแก้ไข ──
    resolve_timeout = "4h" if severity in ("critical", "high") else "8h"

    resolved = await step.wait_for_event(
        "wait-resolve",
        event="incident.resolved",
        if_exp=f"async.data.incident_id == {incident_id}",
        timeout=resolve_timeout,
    )

    if not resolved:
        await step.run("notify-resolve-timeout", lambda: send_notification(
            "all",
            f"⏰ เหตุการณ์ #{incident_id} ยังไม่ได้แก้ไขใน {resolve_timeout}",
            incident_id=incident_id,
        ))
        return {"status": "resolve_timeout", "incident_id": incident_id}

    # ── Step 7: อัพเดท state → resolved ──
    await step.run("mark-resolved", lambda: odoo_rpc(
        "patrol.incident", "write",
        [[incident_id], {
            "state": "resolved",
            "resolution_note": resolved.data.get("note", ""),
        }],
    ))

    # ── Step 8: แจ้งปิดเหตุการณ์ ──
    resolution_time = resolved.data.get("resolution_time", "N/A")
    await step.run("notify-resolved", lambda: send_notification(
        "all",
        f"✅ เหตุการณ์ #{incident_id} แก้ไขแล้ว\nเวลา: {resolution_time}",
        incident_id=incident_id,
    ))

    return {"status": "resolved", "incident_id": incident_id}


# ═══════════════════════════════════════════════════════
#  ② MISSION LIFECYCLE
# ═══════════════════════════════════════════════════════

@inngest_client.create_function(
    fn_id="mission-lifecycle",
    trigger=inngest.TriggerEvent(event="mission.activated"),
)
async def mission_lifecycle(ctx: inngest.Context, step: inngest.Step):
    """
    จัดการภารกิจ — แจ้งทุกทีม, เริ่ม equipment, monitor จนเสร็จ
    """
    event = ctx.event
    d = event.data
    mission_id = d.get("mission_id")

    # ── Step 1: ดึงข้อมูลภารกิจ ──
    missions = await step.run("fetch-mission", lambda: odoo_rpc(
        "patrol.mission", "read",
        [[mission_id], ["code", "name", "commander_id", "soldier_ids", "equipment_ids"]],
    ))

    if not missions:
        return {"status": "error", "reason": "mission not found"}

    mission = missions[0]

    # ── Step 2: แจ้งทุกทีม ──
    await step.run("notify-mission-start", lambda: send_notification(
        "all",
        f"📋 ภารกิจ {mission['code']} เริ่มแล้ว!\n"
        f"ชื่อ: {mission['name']}\n"
        f"กำลังพล: {len(mission.get('soldier_ids', []))} นาย\n"
        f"อุปกรณ์: {len(mission.get('equipment_ids', []))} ชิ้น",
        mission_id=mission_id,
    ))

    # ── Step 3: เริ่ม equipment ทั้งหมด (สั่ง Node.js) ──
    if mission.get("equipment_ids"):
        equipment_list = await step.run("fetch-equipment", lambda: odoo_rpc(
            "patrol.equipment", "read",
            [mission["equipment_ids"], ["name", "stream_path", "capture_interval"]],
        ))

        for eq in (equipment_list or []):
            if eq.get("stream_path"):
                await step.run(f"start-{eq['name']}", lambda: start_camera(
                    eq["name"], eq["stream_path"], eq.get("capture_interval", 2000),
                ))

    # ── Step 4: รอภารกิจเสร็จ ──
    completed = await step.wait_for_event(
        "wait-mission-complete",
        event="mission.completed",
        if_exp=f"async.data.mission_id == {mission_id}",
        timeout="24h",
    )

    # ── Step 5: หยุด equipment ──
    if mission.get("equipment_ids"):
        equipment_list = await step.run("fetch-equipment-stop", lambda: odoo_rpc(
            "patrol.equipment", "read",
            [mission["equipment_ids"], ["name"]],
        ))
        for eq in (equipment_list or []):
            await step.run(f"stop-{eq['name']}", lambda: stop_camera(eq["name"]))

    # ── Step 6: สรุปผล ──
    incidents = await step.run("fetch-incidents", lambda: odoo_rpc(
        "patrol.incident", "search_count",
        [[["mission_id", "=", mission_id]]],
    ))

    await step.run("notify-mission-complete", lambda: send_notification(
        "all",
        f"🏁 ภารกิจ {mission['code']} {'เสร็จสิ้น' if completed else 'หมดเวลา'}\n"
        f"เหตุการณ์ทั้งหมด: {incidents or 0} รายการ",
        mission_id=mission_id,
    ))

    return {
        "status": "completed" if completed else "timeout",
        "mission_id": mission_id,
        "incidents": incidents or 0,
    }


async def start_camera(name, stream_path, interval_ms):
    """สั่ง Node.js เริ่มดึง frame"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{NODE_SERVICE_URL}/api/camera/start", json={
                "cameraId": name,
                "rtspPath": stream_path,
                "intervalMs": interval_ms,
            }, timeout=10)
        except Exception as e:
            print(f"[WARN] start_camera {name}: {e}")


async def stop_camera(name):
    """สั่ง Node.js หยุดดึง frame"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{NODE_SERVICE_URL}/api/camera/stop", json={
                "cameraId": name,
            }, timeout=10)
        except Exception as e:
            print(f"[WARN] stop_camera {name}: {e}")


# ═══════════════════════════════════════════════════════
#  ③ DAILY REPORT
# ═══════════════════════════════════════════════════════

@inngest_client.create_function(
    fn_id="daily-report",
    trigger=inngest.TriggerCron(cron="0 8 * * *"),
)
async def daily_report(ctx: inngest.Context, step: inngest.Step):
    """สรุปรายงานประจำวัน — ทุก module"""

    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    incidents = await step.run("count-incidents", lambda: odoo_rpc(
        "patrol.incident", "search_count",
        [[["date_reported", ">=", yesterday]]],
    ))

    missions = await step.run("count-missions", lambda: odoo_rpc(
        "patrol.mission", "search_count",
        [[["state", "=", "active"]]],
    ))

    await step.run("send-report", lambda: send_notification(
        "all",
        f"📊 รายงานประจำวัน\n"
        f"เหตุการณ์เมื่อวาน: {incidents or 0}\n"
        f"ภารกิจที่กำลังดำเนินการ: {missions or 0}",
    ))

    return {"incidents": incidents, "missions": missions}


# ═══════════════════════════════════════════════════════
#  FastAPI App
# ═══════════════════════════════════════════════════════

app = FastAPI(title="NAVI-CC Inngest Worker")

inngest.fast_api.serve(
    app,
    inngest_client,
    [incident_lifecycle, mission_lifecycle, daily_report],
)


@app.get("/health")
async def health():
    return {"status": "ok", "app": "navi-cc", "functions": 3}
