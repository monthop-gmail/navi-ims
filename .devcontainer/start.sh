#!/bin/bash
# ═══ Every start (postStartCommand) ═══
set -e

echo "🔄 NAVI-CC — Starting services..."

# Wait for services to be ready
echo "⏳ Waiting for Odoo database..."
for i in $(seq 1 30); do
    if docker compose -f /workspace/docker-compose.yml exec -T postgres-odoo pg_isready -U odoo 2>/dev/null; then
        echo "✅ PostgreSQL ready"
        break
    fi
    sleep 2
done

# Check if Odoo DB is initialized
DB_INIT=$(docker compose -f /workspace/docker-compose.yml exec -T postgres-odoo psql -U odoo -d odoo -tAc "SELECT 1 FROM ir_module_module LIMIT 1" 2>/dev/null || echo "")
if [ -z "$DB_INIT" ]; then
    echo "📦 Initializing Odoo database + patrol_command module..."
    docker compose -f /workspace/docker-compose.yml run --rm odoo odoo -i base,patrol_command --stop-after-init -d odoo
    docker compose -f /workspace/docker-compose.yml restart odoo
    echo "✅ Odoo initialized"
else
    echo "✅ Odoo database already initialized"
fi

# Set ports public if in Codespace
if [ -n "$CODESPACE_NAME" ]; then
    echo "🌐 Setting port visibility..."
    gh codespace ports visibility 8069:public 3000:public 8888:public 3100:public -c "$CODESPACE_NAME" 2>/dev/null || true
    echo "✅ Ports set to public"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  NAVI-CC — Patrol Command Center"
echo "════════════════════════════════════════════"
echo ""
echo "  🌐 Odoo:        https://${CODESPACE_NAME}-8069.app.github.dev"
echo "  📱 Soldier page: https://${CODESPACE_NAME}-3000.app.github.dev/patrol/soldier.html"
echo "  📹 HLS Video:   https://${CODESPACE_NAME}-8888.app.github.dev"
echo "  📊 Inngest:     https://${CODESPACE_NAME}-8288.app.github.dev"
echo "  📋 Bull Board:  https://${CODESPACE_NAME}-3100.app.github.dev"
echo ""
echo "  Login: admin / admin"
echo "════════════════════════════════════════════"
