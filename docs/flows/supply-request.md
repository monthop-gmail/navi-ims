# Flow: Supply Request — เบิกพัสดุ

> ขอเบิก → อนุมัติตามสายบัญชาการ → เบิกจ่าย → stock ลดอัตโนมัติ

## Diagram

```mermaid
flowchart TD
    A[ทหาร/ผบ. สร้างใบเบิก<br/>REQ-2026-xxxx] --> B[เพิ่มรายการพัสดุ<br/>+ จำนวน]
    B --> C[กด ส่งขออนุมัติ<br/>state=submitted]
    C --> D{ผบ. อนุมัติ?}
    D -->|อนุมัติ| E[state=approved]
    D -->|ไม่อนุมัติ| F[state=rejected]
    E --> G[กด เบิกจ่าย]
    G --> H{stock พอ?}
    H -->|พอ| I[ลด stock อัตโนมัติ<br/>state=done]
    H -->|ไม่พอ| J[❌ Error:<br/>stock ไม่พอ]
    I --> K[✅ จบ]
```

## Spec

```yaml
flow:
  name: supply-request
  description: เบิกพัสดุ + อนุมัติ + ลด stock
  version: 1

trigger:
  type: manual
  who: soldier | squad_leader | platoon_leader

states:
  - draft → submitted → approved → done
  - submitted → rejected

steps:
  - id: create
    name: สร้างใบเบิก
    model: patrol.supply.request
    fields: [request_type, soldier_id, unit_id, mission_id, line_ids]

  - id: submit
    name: ส่งขออนุมัติ
    state: draft → submitted

  - id: approve
    name: อนุมัติ
    state: submitted → approved
    who: squad_leader | platoon_leader | company_commander
    fields_updated: [approved_by = current_user]

  - id: issue
    name: เบิกจ่าย
    state: approved → done
    validation: ทุก line.item_id.quantity >= line.quantity
    side_effects:
      - item.quantity -= line.quantity สำหรับทุก line

  - id: reject
    name: ไม่อนุมัติ
    state: submitted → rejected

models_involved:
  - model: patrol.supply.request
    operations: [create, read, write]
  - model: patrol.supply.request.line
    operations: [create, read]
  - model: patrol.supply.item
    operations: [read, write]
```
