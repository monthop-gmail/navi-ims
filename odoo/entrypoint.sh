#!/bin/bash
# ═══ Odoo Entrypoint — auto-init if DB empty ═══

MODULES="base,patrol_command,patrol_intelligence,patrol_personnel,patrol_inventory,patrol_geofence,patrol_access,patrol_geolocation"

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if pg_isready -h postgres-odoo -U odoo -q 2>/dev/null; then
        echo "✅ PostgreSQL ready"
        break
    fi
    sleep 2
done

# Check if DB needs init
DB_EXISTS=$(psql -h postgres-odoo -U odoo -d odoo -tAc "SELECT 1 FROM ir_module_module LIMIT 1" 2>/dev/null || echo "")

if [ -z "$DB_EXISTS" ]; then
    echo "📦 First run — initializing Odoo + all modules (~2 min)..."
    odoo -i "$MODULES" --stop-after-init -d odoo
    echo "✅ Database initialized"
fi

# Start Odoo normally
echo "🚀 Starting Odoo..."
exec odoo "$@"
