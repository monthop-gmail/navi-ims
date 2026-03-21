# NAVI-IMS — Integrated Management System

ระบบจัดการแบบบูรณาการ บน Odoo 19 — ศูนย์บัญชาการ, GPS Tracking, Live Video, AI Detection, Access Control, Geolocation และอื่นๆ

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/monthop-gmail/navi-ims?quickstart=1)

## สถาปัตยกรรม

```
┌──────────────────────────────────────────────────────────────┐
│                     Odoo 19 (NAVI-IMS)                       │
│                                                              │
│  patrol_command (core)    ศูนย์บัญชาการ, ภารกิจ, กำลังพล      │
│  patrol_personnel         ฝึกอบรม, ตารางเวร, สุขภาพ           │
│  patrol_inventory         คลังพัสดุ, เบิก-จ่าย                │
│  patrol_intelligence      ข่าวกรอง, Watchlist, พื้นที่เสี่ยง   │
│  patrol_geofence          เขตพื้นที่, แจ้งเตือนเข้า-ออกเขต    │
│  patrol_access            เข้า-ออก, ทะเบียนคน/รถ, ประตู       │
│  patrol_geolocation       พิกัดจริงจากกล้อง, Camera Calibration│
│                                                              │
│  Command Center: แผนที่ Leaflet + Live Video (WHEP)           │
│    + Sighting markers + Gate status + World Tracking          │
└──────────┬───────────────────────────────────────────────────┘
           │
     ┌─────┼──────────┬──────────────┬──────────────┐
     ▼     ▼          ▼              ▼              ▼
  MediaMTX  Node.js   Celery       Inngest       PostgreSQL
  (stream)  (Bull)    (AI)         (workflow)    (Odoo DB)
```

## Modules

| Module | ติดตั้ง | คำอธิบาย |
|--------|---------|----------|
| **patrol_command** | บังคับ | Core: หน่วย, กำลังพล, อุปกรณ์, ภารกิจ, GPS, เหตุการณ์, ซ่อมบำรุง, Command Center, Executive Dashboard, Notification (LINE/Slack/Discord) |
| **patrol_personnel** | เลือกได้ | ประวัติฝึก + ใบรับรอง, ตารางเวร, สุขภาพ + ความพร้อม |
| **patrol_inventory** | เลือกได้ | คลังพัสดุ (อาวุธ/กระสุน/เสบียง/อะไหล่), ใบเบิก-จ่าย + อนุมัติ |
| **patrol_intelligence** | เลือกได้ | Watchlist (บุคคล/รถ/เรือ), รายงานข่าวกรอง (INTSUM), พื้นที่เสี่ยง |
| **patrol_geofence** | เลือกได้ | กำหนดเขต (วงกลม/polygon), แจ้งเตือนเข้า-ออก, สร้าง incident อัตโนมัติ |
| **patrol_access** | เลือกได้ | ทะเบียนคน/รถ/เรือ, ประตู/ท่าเรือ/ปากร่องน้ำ, เปิดอัตโนมัติ, สอดส่อง (Sighting) |
| **patrol_geolocation** | เลือกได้ | Camera Calibration, แปลง pixel→พิกัดจริง, Sensor Fusion, World Tracking ข้ามกล้อง |

## แหล่งภาพ 3 ประเภท

| ประเภท | Protocol | ลักษณะ |
|--------|----------|--------|
| กล้อง Fixed (Dahua NVR) | RTSP | 24/7 — ประตู, ในพื้นที่, ปากร่องน้ำ, ท่าเรือ |
| Drone Cam | RTMP push → MediaMTX | เฉพาะภารกิจ |
| Body Cam ทหาร | WebRTC/WHIP → MediaMTX | เฉพาะภารกิจ |

## Services

| Service | Port | หน้าที่ |
|---------|------|---------|
| **Odoo 19** | `8069` | ศูนย์กลางข้อมูลทั้งหมด |
| **MediaMTX** | `8554` `1935` `8889` `8888` | รวม stream กล้อง (RTSP/RTMP/WebRTC/HLS) |
| **Node.js + Bull** | `3000` | ดึง frame + GPS relay (Socket.IO) |
| **Inngest** | `8288` | Shared workflow engine |
| **Inngest Worker** | `8100` | รัน workflow functions |
| **Celery Worker** | — | AI วิเคราะห์ภาพ + video processing |
| **PostgreSQL** x2 | — | Database สำหรับ Odoo + Inngest |
| **Redis** | — | Queue สำหรับ Celery + Bull |
| **Bull Board** | `3100` | UI ดูสถานะคิว |

## Quick Start

### GitHub Codespaces (แนะนำ)

1. กดปุ่ม **Open in GitHub Codespaces** ด้านบน (หรือ Code → Codespaces → Create)
2. รอ container สร้างเสร็จ (~1 นาที)
3. Terminal จะรัน `docker compose up -d --build` อัตโนมัติ (~3-5 นาที)
4. Odoo จะ auto-init DB + ลง 7 modules เอง (~30 วินาที)
5. ไปที่ tab **PORTS** ด้านล่าง → คลิก globe icon ของ port **8069**
6. Login: **admin / admin**

> **หมายเหตุ:** ใน Codespaces ไม่ใช้ `localhost` — ดู URL จาก tab PORTS

### Docker Compose (Local)

```bash
git clone https://github.com/monthop-gmail/navi-ims.git
cd navi-ims
cp .env.example .env

# Start ทุก service (ครั้งแรก Odoo จะ auto-init DB + ลง 7 modules ~30 วินาที)
docker compose up -d --build
```

เปิด http://localhost:8069 → Login: **admin / admin**

## ทดสอบ

### 1. Command Center (แผนที่)

เมนู **ปฏิบัติการ** → **ศูนย์บัญชาการ**

- แผนที่ dark theme + marker: กำลังพล, อุปกรณ์, SOS, ประตู, การพบเห็น
- Sidebar: รายชื่อทหาร, สถิติ, เหตุการณ์
- ปุ่ม **👁 สอดส่อง**: แสดง/ซ่อน marker การพบเห็น + legend สี
- ปุ่ม **📹 Grid**: สลับโหมด video grid
- Auto-refresh ทุก 5 วินาที

### 2. ทหารลาดตะเวน (มือถือ)

เปิด `http://localhost:3000/patrol/soldier.html` บนมือถือ

1. ใส่ callsign (เช่น `Alpha-1`) → กด **เริ่มลาดตะเวน**
2. อนุญาตกล้อง + GPS → ส่ง video (WHIP) + GPS (Socket.IO) ไป server
3. กดค้าง **SOS** (1 วินาที) → สร้าง incident + Inngest workflow อัตโนมัติ

### 3. Live Video

- Click marker บนแผนที่ → video popup (WHEP)
- กดปุ่ม **📹 Grid** → แสดง video ทุกคนที่ online
- Layout อัตโนมัติ: 1/2/4/9 ช่อง

### 4. ภารกิจ

1. สร้างภารกิจ → มอบหมายกำลังพล + อุปกรณ์
2. กด **เริ่มปฏิบัติการ** → เริ่ม stream กล้อง + แจ้งทุกทีมผ่าน Inngest
3. กด **เสร็จสิ้น** → หยุด stream + สรุปผล

### 5. เหตุการณ์ / Incident

- สร้างจาก: SOS, AI detection, geofence, manual
- Workflow: ใหม่ → มอบหมาย → ดำเนินการ → แก้ไข → ปิด
- Escalate อัตโนมัติตามสายบัญชาการ

### 6. เข้า-ออก / Access Control

- **ทะเบียนบุคคล/รถ/เรือ**: รูปถ่าย, สิทธิ์, วันหมดอายุ
- **ประตู/ท่าเรือ/ปากร่องน้ำ**: ตั้งนโยบาย เปิดอัตโนมัติ/รออนุมัติ/บล็อก
- **คำขอเข้า-ออก** (Kanban): กดอนุมัติ → เปิดประตู + บันทึกเข้าทะเบียน

### 7. สอดส่อง / Sighting

- กล้องในพื้นที่บันทึกทุกคน/รถ/เรือที่ผ่าน
- กล้องปากร่องน้ำ/ท่าเรือ ตรวจจับเรือเข้า-ออก
- Match กับทะเบียน + Watchlist อัตโนมัติ
- ตั้งกฎแจ้งเตือน → สร้าง incident เมื่อตรงเงื่อนไข

### 8. Geolocation / World Tracking

- Camera Calibration: ตั้งค่ากล้อง (ตำแหน่ง, ทิศ, FOV, ความสูง)
- AI ส่ง bounding box → ได้พิกัดจริง (±5-20m)
- Sensor Fusion: ถ้ารู้จักทหารที่ online → ใช้ GPS จริงแทน (±5m)
- World Tracking: ติดตามคน/รถ/เรือข้ามหลายกล้อง + ดูเส้นทางย้อนหลัง

### 9. Executive Dashboard

- KPI: กำลังพลพร้อม%, อุปกรณ์พร้อม%, เหตุการณ์, เวลาตอบสนอง
- Trend chart: เหตุการณ์ 14 วัน
- แยกตามประเภท + ความรุนแรง
- ค่าซ่อมบำรุง/เดือน

### 10. Notification (LINE/Slack/Discord)

- ตั้งค่า: ตั้งค่า → ช่องทางแจ้งเตือน
- รองรับ: LINE Notify, Slack Webhook, Discord Webhook, Odoo Internal
- กรองตาม severity + ประเภทเหตุการณ์
- ประวัติส่งทั้งหมด + สถานะสำเร็จ/ล้มเหลว

## Data Flow

```
📱 ทหาร (มือถือ)
  ├── Video (WHIP) ──→ MediaMTX ──→ WHEP subscribe ──→ Odoo Dashboard
  ├── GPS (Socket.IO) ──→ Node.js ──→ Odoo (patrol.gps.log)
  ├── SOS ──→ Node.js ──→ Odoo (patrol.incident) ──→ Inngest workflow
  └── GPS ──→ Geofence check ──→ ละเมิดเขต? ──→ Odoo incident

📷 กล้อง Fixed — ประตู/ในพื้นที่
  ├── RTSP ──→ MediaMTX ──→ Node.js ดึง frame ──→ Celery AI
  ├── AI ตรวจจับ anomaly ──→ Odoo incident ──→ Inngest workflow
  ├── AI ตรวจจับคน/รถ ──→ Geolocation (pixel→พิกัด) ──→ Sighting + World Track
  ├── Match ทะเบียนคน/รถ ──→ รู้จัก / ไม่รู้จัก / Watchlist
  └── ที่ประตู ──→ Access Control ──→ เปิดอัตโนมัติ / บล็อก / รออนุมัติ

📷 กล้อง Fixed — ปากร่องน้ำ/ท่าเรือ
  ├── AI ตรวจจับเรือ ──→ Match ทะเบียนเรือ
  ├── รู้จัก ──→ Sighting (บันทึก) + World Track
  ├── ไม่รู้จัก ──→ Sighting + เช็คกฎแจ้งเตือน ──→ สร้าง incident?
  └── Watchlist ──→ 🚨 Sighting + incident + แจ้ง LINE/Slack ทันที

🚁 Drone
  ├── Video (RTMP) ──→ MediaMTX ──→ Node.js ดึง frame ──→ Celery AI
  ├── AI ตรวจจับ ──→ Geolocation + Sighting + World Track
  └── GPS (tracker) ──→ Odoo GPS Server (HTTP/OsmAnd/Traccar)

⚙️ Inngest Workflow (shared — ทุก module ใช้ร่วมกัน)
  incident.created ──→ หา commander (ตามสายบัญชาการ)
    ──→ แจ้งเตือน (LINE/Slack/Discord/Odoo)
    ──→ รอรับงาน (15-30 นาที)
    ──→ timeout? ──→ escalate ไปหน่วยเหนือ
    ──→ รอแก้ไข ──→ ปิด incident

  mission.activated ──→ แจ้งทุกทีม (LINE/Slack)
    ──→ เริ่ม stream กล้อง/อุปกรณ์ทั้งหมด
    ──→ monitor ──→ เสร็จ ──→ หยุด stream + สรุปผล

📊 Executive Dashboard
  ──→ รวม KPI จากทุก module อัตโนมัติ
  ──→ กำลังพลพร้อม%, อุปกรณ์พร้อม%, เหตุการณ์, เวลาตอบสนอง
  ──→ Trend chart + แยกตามประเภท/ความรุนแรง
```

## Command Center — Marker สีบนแผนที่

| สี | Icon | ความหมาย |
|----|------|----------|
| 🟢 เขียว | ● | ทหาร online |
| ⚫ เทา | ● | ทหาร offline |
| 🔵 น้ำเงิน | 👤 | เจ้าหน้าที่ (sighting) |
| 🟣 ม่วง | ⭐ | VIP (sighting) |
| 🟡 เหลือง | 🧑 | ผู้มาติดต่อ (sighting) |
| ⚫ ดำ | 🚗 | รถ (sighting) |
| 🔵 น้ำเงินเข้ม | 🚢 | เรือรู้จัก |
| 🔵 ฟ้าอ่อน | ⛵ | เรือไม่รู้จัก |
| ⚫ เทา | ❓ | ไม่รู้จัก (sighting) |
| 🔴 แดง | 🚨 | Watchlist / SOS |
| 🟢/🟠 | 🔓/🔒 | ประตู/ท่าเรือ เปิด/ปิด |
| 🔵 | 📷 | กล้อง Fixed |
| 🟠 | 🚁 | Drone |

## Security (Role-Based Access)

| บทบาท | สิทธิ์ |
|--------|--------|
| **ทหาร** (pvt-cpl) | ดูของตัวเอง, แจ้งซ่อม, รายงานเหตุการณ์ |
| **ผบ.หมู่** (sgt) | + ดูทหารในหมู่, จัดการเหตุการณ์ |
| **ผบ.หมวด** (lt) | + ดูทั้งหมวด, สร้างภารกิจ, จัดการอุปกรณ์ |
| **ผบ.กองร้อย** (cpt+) | ดูทุกอย่าง, ตั้งค่าระบบ |

## โครงสร้างไฟล์

```
navi-ims/
├── .devcontainer/              # GitHub Codespaces
├── docker-compose.yml          # 10 services
├── .env.example
│
├── odoo/addons/
│   ├── patrol_command/         # Core module (บังคับ)
│   ├── patrol_personnel/       # กำลังพล (เลือกได้)
│   ├── patrol_inventory/       # คลังพัสดุ (เลือกได้)
│   ├── patrol_intelligence/    # ข่าวกรอง (เลือกได้)
│   ├── patrol_geofence/        # เขตพื้นที่ (เลือกได้)
│   ├── patrol_access/          # เข้า-ออก + สอดส่อง (เลือกได้)
│   └── patrol_geolocation/     # พิกัดจริง + World Tracking (เลือกได้)
│
├── inngest-worker/             # Shared workflow engine
├── celery-worker/              # AI + Video processing
├── node-service/               # Camera ingest + GPS relay
│   ├── src/
│   │   ├── index.mjs
│   │   └── gps-relay.mjs
│   └── public/
│       └── soldier.html        # Mobile page
│
└── mediamtx/
    └── mediamtx.yml            # Media server config
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
