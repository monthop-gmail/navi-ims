# NAVI-IMS Flow Definitions

## วิธีใช้

ไฟล์ในโฟลเดอร์นี้คือ **flow definitions** ที่ทั้งคนและ AI อ่านได้:

- **คน** → วาด diagram ใน [draw.io](https://app.diagrams.net/) ตามปกติ
- **AI Coding Agent** → อ่าน .drawio XML + YAML spec → implement ได้ทันที
- **Version Control** → review, comment, approve ผ่าน PR ได้

## โครงสร้าง

```
docs/flows/
├── README.md                  ← ไฟล์นี้
├── _template.md               ← Template สำหรับ flow ใหม่
├── diagrams/                  ← ไฟล์ draw.io + SVG export
│   ├── sos-incident.drawio    ← ต้นฉบับ (ทีมวาด)
│   ├── sos-incident.svg       ← export สำหรับดูบน GitHub
│   └── ...
├── sos-incident.md            ← YAML spec + Mermaid + Notes
└── ...
```

| ส่วน | ใครทำ | คนอ่าน | AI อ่าน |
|------|-------|--------|---------|
| **draw.io diagram** | ทีมวาด | เปิดใน draw.io / ดู SVG | อ่าน XML structure |
| **SVG export** | ทีม export | ดูบน GitHub ได้เลย | — |
| **Mermaid diagram** | ทีม หรือ AI สร้างจาก .drawio | GitHub render ภาพ | อ่าน code |
| **YAML spec** | ทีม หรือ AI สร้างจาก .drawio | อ่านได้ | parse → implement |

## วิธีเขียน flow ใหม่

### วิธีที่ 1: ทีมวาดใน draw.io (แนะนำ)

1. วาด flow ใน [app.diagrams.net](https://app.diagrams.net/)
2. **File → Save as** → บันทึกเป็น `docs/flows/diagrams/xxx.drawio`
3. **File → Export as → SVG** → บันทึกเป็น `docs/flows/diagrams/xxx.svg`
4. Commit ทั้ง `.drawio` + `.svg` เข้า repo
5. บอก AI:

> "อ่าน `docs/flows/diagrams/xxx.drawio` แล้วสร้าง spec ใน `docs/flows/xxx.md`"

AI จะ:
- Parse .drawio XML → เข้าใจ flow
- สร้าง Mermaid diagram + YAML spec อัตโนมัติ
- เขียน `xxx.md` ให้ครบ → พร้อม implement

### วิธีที่ 2: เขียน Markdown ตรง

1. Copy template จาก `_template.md`
2. วาด Mermaid diagram (preview ที่ [mermaid.live](https://mermaid.live))
3. เติม YAML spec ให้ครบ
4. Commit → ส่งให้ AI implement ได้เลย

### วิธีที่ 3: อธิบายด้วยคำพูด

บอก AI ว่า flow ทำงานยังไง → AI สร้าง diagram + spec + implement ให้ทั้งหมด

## Flow ทั้งหมด

| ไฟล์ | Flow | สถานะ |
|------|------|-------|
| [sos-incident.md](sos-incident.md) | SOS → Incident → Escalate → Resolve | ใช้งานจริง |
| [ai-detection.md](ai-detection.md) | กล้อง → AI → Incident → Resolve | ใช้งานจริง |
| [mission-lifecycle.md](mission-lifecycle.md) | สร้าง → วางแผน → ปฏิบัติ → เสร็จ | ใช้งานจริง |
| [access-control.md](access-control.md) | กล้อง → จดจำ → เปิดประตู/บล็อก | ใช้งานจริง |
| [maintenance.md](maintenance.md) | แจ้งซ่อม → มอบหมาย → ซ่อม → ตรวจรับ | ใช้งานจริง |
| [supply-request.md](supply-request.md) | ขอเบิก → อนุมัติ → เบิกจ่าย | ใช้งานจริง |
| [_template.md](_template.md) | Template สำหรับ flow ใหม่ | — |

## Tips

- **ตั้งชื่อ .drawio ให้ตรงกับ .md** เช่น `sos-incident.drawio` ↔ `sos-incident.md`
- **.drawio คือต้นฉบับ** — แก้ที่ draw.io แล้ว export SVG ใหม่
- **YAML spec คือสิ่งที่ AI ใช้** — ยิ่งละเอียดยิ่ง implement ได้แม่น
- **VS Code มี draw.io extension** — แก้ .drawio ใน editor ได้เลย: [hediet.vscode-drawio](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)
