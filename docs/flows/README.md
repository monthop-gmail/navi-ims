# NAVI-IMS Flow Definitions

## วิธีใช้

ไฟล์ในโฟลเดอร์นี้คือ **flow definitions** ที่ทั้งคนและ AI อ่านได้:

- **คน** → เห็น diagram บน GitHub (Mermaid renders อัตโนมัติ)
- **AI Coding Agent** → อ่าน YAML spec → implement ได้ทันที
- **Version Control** → review, comment, approve ผ่าน PR ได้

## โครงสร้าง

แต่ละ flow มี 3 ส่วน:

```
1. Diagram (Mermaid)     → คนดูเข้าใจ flow
2. Spec (YAML block)     → AI อ่านได้ มี trigger, steps, models, events
3. Notes                 → เงื่อนไข, edge cases, ข้อจำกัด
```

## วิธีเขียน flow ใหม่

1. Copy template จาก `_template.md`
2. วาด Mermaid diagram
3. เติม YAML spec ให้ครบ
4. Commit → ส่งให้ AI implement ได้เลย

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
