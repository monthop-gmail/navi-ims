# Flow: Equipment Maintenance

> อุปกรณ์เสีย/ครบกำหนดซ่อม → แจ้งซ่อม → มอบหมายช่าง → ซ่อม → ตรวจรับ → พร้อมใช้

## Diagram

```mermaid
flowchart TD
    A{แหล่งที่มา?}
    A -->|เสีย| B[แจ้งซ่อม corrective<br/>อุปกรณ์ → state=maintenance]
    A -->|ครบกำหนด| C[แผนซ่อมบำรุง<br/>กดปุ่มสร้างใบแจ้งซ่อม]
    A -->|ตรวจสภาพ| D[แจ้งซ่อม inspection]
    B --> E[MNT-2026-xxxx<br/>state=new]
    C --> E
    D --> E
    E --> F[เลือกช่างผู้รับผิดชอบ]
    F --> G[กด มอบหมาย<br/>state=assigned]
    G --> H[กด เริ่มซ่อม<br/>state=in_progress]
    H --> I[บันทึก: สาเหตุ + วิธีแก้<br/>+ อะไหล่ + ค่าใช้จ่าย]
    I --> J[กด ซ่อมเสร็จ<br/>state=done]
    J --> K[กด ตรวจรับ<br/>state=verified]
    K --> L[อุปกรณ์ → state=ready<br/>อัตโนมัติ]
    L --> M[✅ จบ]
```

## Spec

```yaml
flow:
  name: equipment-maintenance
  description: ซ่อมบำรุงอุปกรณ์ครบ loop
  version: 1

trigger:
  type: manual | schedule
  manual: กดสร้างใบแจ้งซ่อม
  schedule: กดจากแผนซ่อมบำรุง (patrol.maintenance.schedule)

states:
  - new → assigned → in_progress → done → verified
  - new → cancelled

steps:
  - id: create-request
    name: สร้างใบแจ้งซ่อม
    model: patrol.maintenance.request
    fields: [equipment_id, maintenance_type, description, priority]
    side_effects:
      - ถ้า corrective → equipment.state = maintenance

  - id: assign
    name: มอบหมายช่าง
    validation: ต้องเลือก technician_id
    state: new → assigned

  - id: start
    name: เริ่มซ่อม
    state: assigned → in_progress
    fields_updated: [start_date = now()]

  - id: done
    name: ซ่อมเสร็จ
    state: in_progress → done
    fields_updated: [end_date = now()]
    record: [cause, resolution, part_ids, labor_cost]

  - id: verify
    name: ตรวจรับ
    state: done → verified
    fields_updated: [verified_by, verified_date]
    side_effects:
      - equipment.state = ready

models_involved:
  - model: patrol.maintenance.request
    operations: [create, read, write]
  - model: patrol.maintenance.part
    operations: [create, read]
  - model: patrol.maintenance.schedule
    operations: [read, write]
  - model: patrol.equipment
    operations: [read, write]
```
