{
    "name": "Patrol Access Control",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "ระบบเข้า-ออก — จดจำคน/รถ, เปิดประตูอัตโนมัติ, อนุมัติผู้ไม่รู้จัก",
    "author": "NAVI-IMS",
    "license": "LGPL-3",
    "depends": ["patrol_command"],
    "data": [
        "security/ir.model.access.csv",
        "views/access_views.xml",
    ],
    "installable": True,
    "application": False,
}
