"""
Inngest Worker — serve Inngest functions ผ่าน FastAPI
Inngest Server จะ HTTP POST มาที่นี่เมื่อต้องรัน function
"""

import os
import inngest
import inngest.fast_api
from fastapi import FastAPI
import httpx
from celery import Celery

# ─── Clients ───

inngest_client = inngest.Inngest(
    app_id="camera-monitoring",
    event_key=os.environ.get("INNGEST_EVENT_KEY"),
    is_production=True,
)

celery_app = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))

ODOO_URL = os.environ.get("ODOO_URL", "http://odoo:8069")

# ─── Helpers ───

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
        return resp.json().get("result")


async def send_notification(message: str, image_path: str = None):
    """ส่งแจ้งเตือน (LINE / Slack — placeholder)"""
    print(f"[NOTIFY] {message} | image={image_path}")


# ─── Inngest Functions ───

@inngest_client.create_function(
    fn_id="anomaly-ticket-workflow",
    trigger=inngest.TriggerEvent(event="anomaly.detected"),
)
async def handle_anomaly(ctx: inngest.Context, step: inngest.Step):
    """
    Workflow ทั้ง lifecycle:
    ตรวจพบ → สร้าง ticket → แจ้งเตือน → รอรับงาน → รอแก้ → AI verify → ปิด
    """
    event = ctx.event

    camera_id = event.data.get("camera_id")
    anomaly_type = event.data.get("type")
    confidence = event.data.get("confidence", 0)
    image_path = event.data.get("image_path")

    # ── Step 1: สร้าง Ticket ใน Odoo ──
    ticket_id = await step.run(
        "create-ticket",
        lambda: odoo_rpc(
            "helpdesk.ticket",
            "create",
            [
                {
                    "name": f"[CAM-{camera_id}] {anomaly_type}",
                    "description": (
                        f"ตรวจพบ: {anomaly_type}\n"
                        f"กล้อง: {camera_id}\n"
                        f"ความมั่นใจ: {confidence:.0%}\n"
                        f"ภาพ: {image_path}"
                    ),
                    "priority": "2" if confidence > 0.9 else "1",
                }
            ],
        ),
    )

    # ── Step 2: แจ้งเตือนทันที ──
    await step.run(
        "notify-team",
        lambda: send_notification(
            message=f"พบ {anomaly_type} ที่กล้อง {camera_id} (confidence: {confidence:.0%})",
            image_path=image_path,
        ),
    )

    # ── Step 3: รอคนรับงาน (ไม่เกิน 30 นาที) ──
    accepted = await step.wait_for_event(
        "wait-accept",
        event="ticket.accepted",
        if_exp=f"async.data.ticket_id == '{ticket_id}'",
        timeout="30m",
    )

    if not accepted:
        # Escalate → แจ้ง manager
        await step.run(
            "escalate",
            lambda: send_notification(f"ESCALATE: Ticket #{ticket_id} ไม่มีคนรับใน 30 นาที"),
        )
        accepted = await step.wait_for_event(
            "wait-manager-accept",
            event="ticket.accepted",
            if_exp=f"async.data.ticket_id == '{ticket_id}'",
            timeout="2h",
        )

    # ── Step 4: รอแก้ไข + ส่งรูปยืนยัน ──
    resolved = await step.wait_for_event(
        "wait-resolve",
        event="ticket.resolved",
        if_exp=f"async.data.ticket_id == '{ticket_id}'",
        timeout="8h",
    )

    if not resolved:
        await step.run(
            "timeout-notify",
            lambda: send_notification(f"TIMEOUT: Ticket #{ticket_id} ยังไม่ถูกแก้ไขใน 8 ชม."),
        )
        return {"status": "timeout", "ticket_id": ticket_id}

    # ── Step 5: สั่ง Celery ตรวจสอบรูปยืนยัน (AI verify) ──
    proof_image = resolved.data.get("proof_image")
    verification = await step.run(
        "ai-verify",
        lambda: celery_app.send_task(
            "tasks.verify_resolution",
            args=[proof_image, anomaly_type],
        ).get(timeout=120),
    )

    # ── Step 6: ปิดหรือเปิดใหม่ ──
    if verification.get("passed"):
        await step.run(
            "close-ticket",
            lambda: odoo_rpc(
                "helpdesk.ticket",
                "write",
                [[ticket_id], {"stage_id": 4}],  # stage "Done"
            ),
        )
        return {"status": "resolved", "ticket_id": ticket_id}
    else:
        await step.run(
            "reopen-ticket",
            lambda: send_notification(
                f"REOPEN: Ticket #{ticket_id} ไม่ผ่าน AI verify — {verification.get('reason')}"
            ),
        )
        return {"status": "reopened", "ticket_id": ticket_id}


@inngest_client.create_function(
    fn_id="daily-anomaly-report",
    trigger=inngest.TriggerCron(cron="0 8 * * *"),  # ทุกวัน 8 โมงเช้า
)
async def daily_report(ctx: inngest.Context, step: inngest.Step):
    """สรุปรายงานความผิดปกติประจำวัน"""

    tickets = await step.run(
        "fetch-yesterday-tickets",
        lambda: odoo_rpc(
            "helpdesk.ticket",
            "search_read",
            [[["create_date", ">=", "2026-03-18 00:00:00"]]],
            {"fields": ["name", "priority", "stage_id", "create_date"]},
        ),
    )

    await step.run(
        "send-report",
        lambda: send_notification(f"รายงานประจำวัน: พบ {len(tickets or [])} เหตุการณ์เมื่อวาน"),
    )


# ─── FastAPI App ───

app = FastAPI(title="Inngest Worker")

inngest.fast_api.serve(app, inngest_client, [handle_anomaly, daily_report])


@app.get("/health")
async def health():
    return {"status": "ok"}
