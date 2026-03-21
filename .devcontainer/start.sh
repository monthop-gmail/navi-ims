#!/bin/bash
# ═══ Every start (postStartCommand) ═══

echo "🔄 NAVI-IMS — Starting services..."

# Find workspace
WORKSPACE="${WORKSPACE_FOLDER:-/workspace}"
cd "$WORKSPACE" 2>/dev/null || cd /workspace 2>/dev/null || true

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
for i in $(seq 1 60); do
    # Find postgres container dynamically
    PG_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "postgres-odoo" | head -1)
    if [ -n "$PG_CONTAINER" ]; then
        if docker exec "$PG_CONTAINER" pg_isready -U odoo 2>/dev/null; then
            echo "✅ PostgreSQL ready ($PG_CONTAINER)"
            break
        fi
    fi
    echo "  waiting... ($i/60)"
    sleep 3
done

# Find containers dynamically
ODOO_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "odoo-1$" | grep -v postgres | head -1)
PG_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "postgres-odoo" | head -1)

if [ -z "$ODOO_CONTAINER" ] || [ -z "$PG_CONTAINER" ]; then
    echo "⚠️ Containers not found. Trying docker compose up..."
    docker compose up -d 2>/dev/null || true
    sleep 10
    ODOO_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "odoo-1$" | grep -v postgres | head -1)
    PG_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "postgres-odoo" | head -1)
fi

if [ -z "$ODOO_CONTAINER" ]; then
    echo "❌ Odoo container not found. Please run: docker compose up -d"
    exit 0
fi

echo "📦 Found containers: odoo=$ODOO_CONTAINER pg=$PG_CONTAINER"

# Check if Odoo DB is initialized
DB_INIT=$(docker exec "$PG_CONTAINER" psql -U odoo -d odoo -tAc "SELECT 1 FROM ir_module_module LIMIT 1" 2>/dev/null || echo "")
if [ -z "$DB_INIT" ]; then
    echo "📦 Initializing Odoo database + all modules (first time, ~2 min)..."
    docker exec "$ODOO_CONTAINER" odoo \
        -i base,patrol_command,patrol_personnel,patrol_inventory,patrol_intelligence,patrol_geofence,patrol_access,patrol_geolocation \
        --stop-after-init -d odoo 2>&1 | tail -5

    docker restart "$ODOO_CONTAINER"
    echo "✅ Odoo initialized with all modules"
    sleep 5
else
    echo "✅ Odoo database already initialized"
fi

# Set ports public if in Codespace
if [ -n "$CODESPACE_NAME" ]; then
    echo "🌐 Setting port visibility to public..."
    gh codespace ports visibility 8069:public 3000:public 8888:public 3100:public 8288:public -c "$CODESPACE_NAME" 2>/dev/null || true
fi

# Print URLs
echo ""
echo "════════════════════════════════════════════"
echo "  NAVI-IMS — Integrated Management System"
echo "════════════════════════════════════════════"
if [ -n "$CODESPACE_NAME" ]; then
echo ""
echo "  🌐 Odoo:         https://${CODESPACE_NAME}-8069.app.github.dev"
echo "  📱 Soldier page:  https://${CODESPACE_NAME}-3000.app.github.dev/patrol/soldier.html"
echo "  📹 HLS Video:    https://${CODESPACE_NAME}-8888.app.github.dev"
echo "  📊 Inngest:      https://${CODESPACE_NAME}-8288.app.github.dev"
echo "  📋 Bull Board:   https://${CODESPACE_NAME}-3100.app.github.dev"
else
echo ""
echo "  🌐 Odoo:         http://localhost:8069"
echo "  📱 Soldier page:  http://localhost:3000/patrol/soldier.html"
echo "  📹 HLS Video:    http://localhost:8888"
echo "  📊 Inngest:      http://localhost:8288"
echo "  📋 Bull Board:   http://localhost:3100"
fi
echo ""
echo "  Login: admin / admin"
echo ""
echo "  💡 In Codespaces: go to PORTS tab → click globe icon on port 8069"
echo "════════════════════════════════════════════"
