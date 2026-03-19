{
    "name": "Patrol Geofence",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "เขตพื้นที่ — geofence alerts, เข้า/ออก เขต, สร้าง incident อัตโนมัติ",
    "author": "NAVI-IMS",
    "license": "LGPL-3",
    "depends": ["patrol_command"],
    "data": [
        "security/ir.model.access.csv",
        "views/geofence_views.xml",
    ],
    "installable": True,
    "application": False,
}
