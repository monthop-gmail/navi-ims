#!/bin/bash
# ═══ Every start (postStartCommand) ═══
set -e

echo "🔄 NAVI-IMS — Starting services..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for Odoo database..."
for i in $(seq 1 60); do
    if docker exec odoo-inngest-postgres-odoo-1 pg_isready -U odoo 2>/dev/null; then
        echo "✅ PostgreSQL ready"
        break
    fi
    # Try alternative container name
    if docker exec navi-ims-postgres-odoo-1 pg_isready -U odoo 2>/dev/null; then
        echo "✅ PostgreSQL ready"
        break
    fi
    echo "  waiting... ($i/60)"
    sleep 3
done

# Find the odoo container name
ODOO_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'odoo-1$' | grep -v postgres | head -1)
PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep postgres-odoo | head -1)

if [ -z "$ODOO_CONTAINER" ] || [ -z "$PG_CONTAINER" ]; then
    echo "⚠️ Could not find Odoo/PostgreSQL containers. Services may still be starting..."
    echo "  Run manually: docker compose run --rm odoo odoo -i base,patrol_command,... --stop-after-init -d odoo"
    exit 0
fi

# Check if Odoo DB is initialized
DB_INIT=$(docker exec "$PG_CONTAINER" psql -U odoo -d odoo -tAc "SELECT 1 FROM ir_module_module LIMIT 1" 2>/dev/null || echo "")
if [ -z "$DB_INIT" ]; then
    echo "📦 Initializing Odoo database + all modules..."
    docker exec "$ODOO_CONTAINER" odoo \
        -i base,patrol_command,patrol_personnel,patrol_inventory,patrol_intelligence,patrol_geofence,patrol_access,patrol_geolocation \
        --stop-after-init -d odoo 2>&1 | tail -5

    # Restart odoo to pick up modules
    docker restart "$ODOO_CONTAINER"
    echo "✅ Odoo initialized with all modules"
else
    echo "✅ Odoo database already initialized"
fi

# Set ports public if in Codespace
if [ -n "$CODESPACE_NAME" ]; then
    echo "🌐 Setting port visibility..."
    gh codespace ports visibility 8069:public 3000:public 8888:public 3100:public 8288:public -c "$CODESPACE_NAME" 2>/dev/null || true
    echo "✅ Ports set to public"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  NAVI-IMS — Integrated Management System"
echo "════════════════════════════════════════════"
if [ -n "$CODESPACE_NAME" ]; then
echo ""
echo "  🌐 Odoo:        https://${CODESPACE_NAME}-8069.app.github.dev"
echo "  📱 Soldier page: https://${CODESPACE_NAME}-3000.app.github.dev/patrol/soldier.html"
echo "  📹 HLS Video:   https://${CODESPACE_NAME}-8888.app.github.dev"
echo "  📊 Inngest:     https://${CODESPACE_NAME}-8288.app.github.dev"
echo "  📋 Bull Board:  https://${CODESPACE_NAME}-3100.app.github.dev"
else
echo ""
echo "  🌐 Odoo:        http://localhost:8069"
echo "  📱 Soldier page: http://localhost:3000/patrol/soldier.html"
echo "  📹 HLS Video:   http://localhost:8888"
echo "  📊 Inngest:     http://localhost:8288"
echo "  📋 Bull Board:  http://localhost:3100"
fi
echo ""
echo "  Login: admin / admin"
echo "════════════════════════════════════════════"
