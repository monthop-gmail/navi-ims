{
    "name": "Patrol Geolocation",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "ระบุพิกัดจริงจากกล้อง — Camera Calibration, Homography, Multi-Camera Tracking, Sensor Fusion",
    "author": "NAVI-IMS",
    "license": "LGPL-3",
    "depends": ["patrol_command", "patrol_access"],
    "data": [
        "security/ir.model.access.csv",
        "views/geolocation_views.xml",
    ],
    "installable": True,
    "application": False,
}
