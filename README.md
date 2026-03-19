# NAVI-CC — Patrol Command Center

ระบบศูนย์บัญชาการลาดตะเวน บน Odoo 19 — รวม GPS Tracking, Live Video, AI Detection, Incident Management และ Equipment Maintenance ในที่เดียว

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/monthop-gmail/navi-cc?quickstart=1)

## สถาปัตยกรรม

```
┌──────────────────────────────────────────────────────────────┐
│                     Odoo 19 (ศูนย์บัญชาการ)                    │
│                                                              │
│  patrol.unit          โครงสร้างหน่วย (กองร้อย/หมวด/หมู่)       │
│  patrol.soldier       ทะเบียนกำลังพล + ยศ + สังกัด             │
│  patrol.equipment     ทะเบียนอุปกรณ์ (กล้อง/drone/body cam)    │
│  patrol.mission       ภารกิจ + มอบหมายคน/อุปกรณ์               │
│  patrol.gps.log       บันทึก GPS (ทหาร + drone)               │
│  patrol.incident      เหตุการณ์/SOS + AI detection             │
│  patrol.maintenance   ซ่อมบำรุง + แผนซ่อม + อะไหล่             │
│                                                              │
│  Command Center:      แผนที่ Leaflet + Live Video (WHEP)      │
└──────────┬───────────────────────────────────────────────────┘
           │
     ┌─────┼──────────┬──────────────┬──────────────┐
     ▼     ▼          ▼              ▼              ▼
  MediaMTX  Node.js   Celery       Inngest       PostgreSQL
  (stream)  (Bull)    (AI)         (workflow)    (Odoo DB)
```

## แหล่งภาพ 3 ประเภท

| ประเภท | Protocol | ลักษณะ |
|--------|----------|--------|
| กล้อง Fixed (Dahua NVR) | RTSP | 24/7 ผ่าน MediaMTX |
| Drone Cam | RTMP push → MediaMTX | เฉพาะภารกิจ |
| Body Cam ทหาร | WebRTC/WHIP → MediaMTX | เฉพาะภารกิจ |

## Services

| Service | Port | หน้าที่ |
|---------|------|---------|
| **Odoo 19** | `8069` | ศูนย์บัญชาการ — ข้อมูลทั้งหมดอยู่ที่นี่ |
| **MediaMTX** | `8554` `1935` `8889` `8888` | รวม stream กล้องทุกประเภท (RTSP/RTMP/WebRTC/HLS) |
| **Node.js + Bull** | `3000` | ดึง frame จาก RTSP + GPS relay (Socket.IO) |
| **Inngest** | `8288` | Shared workflow engine (incident + mission lifecycle) |
| **Inngest Worker** | `8100` | รัน workflow functions |
| **Celery Worker** | — | AI วิเคราะห์ภาพ + video processing |
| **PostgreSQL** x2 | — | Database สำหรับ Odoo + Inngest |
| **Redis** | — | Queue สำหรับ Celery + Bull |
| **Bull Board** | `3100` | UI ดูสถานะคิว |

## Quick Start

### GitHub Codespaces (แนะนำ)

1. กดปุ่ม **Open in GitHub Codespaces** ด้านบน
2. เลือก machine type **4-core** ขึ้นไป
3. รอ build (~5 นาทีครั้งแรก)
4. Odoo เปิดอัตโนมัติที่ port 8069
5. Login: **admin / admin**

### Docker Compose (Local)

```bash
git clone https://github.com/monthop-gmail/navi-cc.git
cd navi-cc
cp .env.example .env

# Start ทุก service
docker compose up -d --build

# Init Odoo database + ติดตั้ง module
docker compose run --rm odoo odoo -i base,patrol_command --stop-after-init -d odoo

# Restart Odoo
docker compose restart odoo
```

เปิด http://localhost:8069 → Login: **admin / admin**

## ทดสอบ

### 1. Command Center (แผนที่)

เปิด Odoo → เมนู **ศูนย์บัญชาการ** → **ศูนย์บัญชาการ**

- แผนที่ dark theme แสดง marker กำลังพล + อุปกรณ์ + SOS
- Sidebar: รายชื่อทหาร online/offline, สถิติ, เหตุการณ์
- Filter ตามภารกิจ
- Auto-refresh ทุก 5 วินาที

### 2. ทหารลาดตะเวน (มือถือ)

เปิด `http://localhost:3000/patrol/soldier.html` บนมือถือ

1. ใส่ callsign (เช่น `Alpha-1`) → กด **เริ่มลาดตะเวน**
2. อนุญาตกล้อง + GPS
3. GPS จะอัพเดทใน Odoo real-time
4. กดค้าง **SOS** (1 วินาที) → สร้าง incident อัตโนมัติ

### 3. Live Video

- Click marker บนแผนที่ → video popup (WHEP)
- กดปุ่ม **📹 Grid** → แสดง video ทุกคนที่ online
- Layout อัตโนมัติ: 1/2/4/9 ช่อง

### 4. ภารกิจ

เมนู **ปฏิบัติการ** → **ภารกิจ**

1. สร้างภารกิจ → มอบหมายกำลังพล + อุปกรณ์
2. กด **เริ่มปฏิบัติการ** → เริ่ม stream กล้อง + แจ้งทุกทีมผ่าน Inngest
3. เหตุการณ์ระหว่างภารกิจบันทึกอัตโนมัติ
4. กด **เสร็จสิ้น** → หยุด stream + สรุปผล

### 5. เหตุการณ์ / SOS

เมนู **ปฏิบัติการ** → **เหตุการณ์** (Kanban board)

- สร้างได้จาก: SOS, AI detection, manual
- Workflow: ใหม่ → มอบหมาย → กำลังดำเนินการ → แก้ไขแล้ว → ปิด
- Escalate อัตโนมัติตามสายบัญชาการ (ผ่าน Inngest)

### 6. ซ่อมบำรุง

เมนู **ซ่อมบำรุง** → **ใบแจ้งซ่อม**

- แจ้งซ่อม → มอบหมายช่าง → ซ่อม → ตรวจรับ → อุปกรณ์กลับเป็น ready
- แผนซ่อมบำรุง: ตั้งรอบ (ทุก 30 วัน ฯลฯ) → สร้างใบแจ้งซ่อมอัตโนมัติ
- บันทึกอะไหล่ + ค่าใช้จ่าย

## Data Flow

```
📱 ทหาร (มือถือ)
  ├── Video (WHIP) ──→ MediaMTX ──→ WHEP subscribe ──→ Odoo Dashboard
  ├── GPS (Socket.IO) ──→ Node.js ──→ Odoo (patrol.gps.log)
  └── SOS ──→ Node.js ──→ Odoo (patrol.incident) ──→ Inngest workflow

📷 กล้อง Fixed (Dahua NVR)
  ├── RTSP ──→ MediaMTX ──→ Node.js ดึง frame
  └── frame ──→ Celery AI ──→ anomaly? ──→ Odoo incident ──→ Inngest

🚁 Drone
  ├── Video (RTMP) ──→ MediaMTX ──→ Node.js ดึง frame ──→ Celery AI
  └── GPS (tracker) ──→ Odoo GPS Server (HTTP/OsmAnd/Traccar)

⚙️ Inngest Workflow
  incident.created ──→ หา commander ──→ แจ้งเตือน ──→ รอรับงาน
    ──→ timeout? escalate ──→ รอแก้ไข ──→ ปิด
  mission.activated ──→ แจ้งทุกทีม ──→ เริ่ม equipment ──→ monitor ──→ สรุปผล
```

## Security (Role-Based Access)

| บทบาท | สิทธิ์ |
|--------|--------|
| **ทหาร** (pvt-cpl) | ดูภารกิจ/อุปกรณ์/เหตุการณ์ของตัวเอง, แจ้งซ่อม, รายงานเหตุการณ์ |
| **ผบ.หมู่** (sgt) | + ดูทหารในหมู่, จัดการเหตุการณ์ |
| **ผบ.หมวด** (lt) | + ดูทั้งหมวด, สร้างภารกิจ, จัดการอุปกรณ์ |
| **ผบ.กองร้อย** (cpt+) | ดูทุกอย่าง, ตั้งค่าระบบ |

ทหารทุกคน login เข้า Odoo ได้ เห็นข้อมูลตามสิทธิ์ของยศ

## GPS Server (Drone)

รองรับ 3 protocol:

| Protocol | Endpoint | ใช้กับ |
|----------|----------|--------|
| HTTP POST JSON | `POST /patrol/api/external/drone_gps` | Custom firmware |
| OsmAnd | `GET /patrol/gps/osmand?id=DRONE-01&lat=..&lon=..` | GPS tracker ทั่วไป |
| Traccar forward | `POST /patrol/api/external/traccar_forward` | Traccar server |

## โครงสร้างไฟล์

```
navi-cc/
├── .devcontainer/              # GitHub Codespaces config
├── docker-compose.yml          # 10 services
├── .env.example                # Environment variables
│
├── odoo/
│   ├── odoo.conf
│   └── addons/
│       └── patrol_command/     # Odoo module
│           ├── models/         # 10 models
│           ├── views/          # List, Form, Kanban, Command Center
│           ├── controllers/    # REST API + External API + GPS Server
│           ├── security/       # Groups + Record Rules + ACL
│           ├── static/src/     # OWL components (Leaflet map, WHEP player)
│           └── data/           # Demo data (units, soldiers, equipment)
│
├── inngest-worker/             # Shared workflow engine (Python/FastAPI)
├── celery-worker/              # AI + Video processing (Python/Celery)
├── node-service/               # Camera ingest + GPS relay (Node.js/Bull)
│   ├── src/
│   │   ├── index.mjs           # Express + Bull + Camera pull
│   │   └── gps-relay.mjs       # Socket.IO GPS relay
│   └── public/
│       └── soldier.html        # Mobile page for soldiers
│
└── mediamtx/
    └── mediamtx.yml            # MediaMTX config (RTSP/RTMP/WebRTC/HLS)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Core** | Odoo 19, PostgreSQL 16, Redis 7 |
| **Workflow** | Inngest (self-hosted) |
| **AI** | Celery + YOLOv8 (placeholder) + OpenCV |
| **Streaming** | MediaMTX (RTSP/RTMP/WebRTC/HLS) |
| **Realtime** | Socket.IO, BullMQ |
| **Frontend** | OWL (Odoo), Leaflet.js, WebRTC (WHIP/WHEP) |
| **Infra** | Docker Compose, GitHub Codespaces |

## License

Private repository.
