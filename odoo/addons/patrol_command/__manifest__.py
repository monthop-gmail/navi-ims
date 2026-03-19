{
    "name": "Patrol Command Center",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "ศูนย์บัญชาการลาดตะเวน — GPS Tracking, Live Video, AI Detection, Incident Management",
    "description": """
        Patrol Command Center (NAVI-CC)
        ================================
        - โครงสร้างหน่วย (กองร้อย/หมวด/หมู่)
        - ทะเบียนกำลังพล + อุปกรณ์
        - ภารกิจ + มอบหมายคน/อุปกรณ์
        - GPS Tracking real-time + replay
        - Incident / SOS management
        - AI anomaly detection integration
        - Inngest workflow orchestration
    """,
    "author": "NAVI-CC",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/patrol_data.xml",
        "views/menu_views.xml",
        "views/patrol_unit_views.xml",
        "views/patrol_soldier_views.xml",
        "views/patrol_equipment_views.xml",
        "views/patrol_mission_views.xml",
        "views/patrol_incident_views.xml",
        "views/patrol_gps_log_views.xml",
    ],
    "installable": True,
    "application": True,
}
