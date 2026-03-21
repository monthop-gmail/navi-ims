#!/bin/bash
# ═══ Every start (postStartCommand) ═══

echo "🔄 NAVI-IMS — Starting services..."

# ─── Find workspace root (where docker-compose.yml lives) ───
if [ -f "/workspaces/navi-ims/docker-compose.yml" ]; then
    WS="/workspaces/navi-ims"
elif [ -f "/workspace/docker-compose.yml" ]; then
    WS="/workspace"
elif [ -f "/workspace/navi-ims/docker-compose.yml" ]; then
    WS="/workspace/navi-ims"
elif [ -n "$WORKSPACE_FOLDER" ] && [ -f "$WORKSPACE_FOLDER/docker-compose.yml" ]; then
    WS="$WORKSPACE_FOLDER"
else
    WS=$(find /workspaces /workspace -maxdepth 2 -name "docker-compose.yml" -printf '%h' -quit 2>/dev/null)
    WS="${WS:-/workspaces/navi-ims}"
fi
echo "📂 Workspace: $WS"
cd "$WS"

# ─── Wait for PostgreSQL ───
echo "⏳ Waiting for PostgreSQL..."
for i in $(seq 1 60); do
    PG_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "postgres-odoo" | head -1)
    if [ -n "$PG_CONTAINER" ]; then
        if docker exec "$PG_CONTAINER" pg_isready -U odoo 2>/dev/null; then
            echo "✅ PostgreSQL ready ($PG_CONTAINER)"
            break
        fi
    fi
    if [ "$i" -eq 60 ]; then
        echo "❌ PostgreSQL not ready after 3 min"
        echo "💡 Try: docker compose up -d && bash .devcontainer/start.sh"
        exit 0
    fi
    sleep 3
done

# ─── Check if DB needs init ───
PG_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "postgres-odoo" | head -1)
DB_INIT=$(docker exec "$PG_CONTAINER" psql -U odoo -d odoo -tAc "SELECT 1 FROM ir_module_module LIMIT 1" 2>/dev/null || echo "")

if [ -z "$DB_INIT" ]; then
    echo "📦 Initializing Odoo database + all modules (first time, ~2 min)..."

    # ใช้ docker compose run แทน docker exec (ปลอดภัยกว่า)
    docker compose -f "$WS/docker-compose.yml" run --rm odoo odoo \
        -i base,patrol_command,patrol_intelligence,patrol_personnel,patrol_inventory,patrol_geofence,patrol_access,patrol_geolocation \
        --stop-after-init -d odoo 2>&1 | tail -10

    if [ $? -eq 0 ]; then
        echo "✅ Odoo initialized with all modules"
    else
        echo "⚠️ Init had errors — check logs: docker compose logs odoo"
    fi

    # Restart Odoo เพื่อให้ใช้งานได้
    ODOO_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -v postgres | grep "odoo" | head -1)
    if [ -n "$ODOO_CONTAINER" ]; then
        docker restart "$ODOO_CONTAINER" 2>/dev/null
    fi
    sleep 5
else
    echo "✅ Odoo database already initialized"

    # เช็คว่า module ครบไหม
    MODULES=$(docker exec "$PG_CONTAINER" psql -U odoo -d odoo -tAc "SELECT count(*) FROM ir_module_module WHERE name LIKE 'patrol%' AND state='installed'" 2>/dev/null || echo "0")
    echo "   Patrol modules installed: $MODULES"
fi

# ─── Set ports public ───
if [ -n "$CODESPACE_NAME" ]; then
    echo "🌐 Setting port visibility to public..."
    gh codespace ports visibility 8069:public 3000:public 8888:public 3100:public 8288:public -c "$CODESPACE_NAME" 2>/dev/null || true
fi

# ─── Print URLs ───
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
