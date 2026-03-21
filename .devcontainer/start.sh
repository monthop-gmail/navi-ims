#!/bin/bash
# ═══ Every start (postStartCommand) ═══
echo "🔄 NAVI-IMS — Starting services..."

# Wait for Docker daemon
for i in $(seq 1 30); do
    if docker info &>/dev/null; then
        break
    fi
    echo "  waiting for Docker... ($i/30)"
    sleep 2
done

# Start all services
echo "📦 Starting Docker Compose..."
docker compose up -d --build 2>&1 | tail -20

# Wait for Odoo to be ready (entrypoint.sh handles DB init automatically)
echo "⏳ Waiting for Odoo..."
for i in $(seq 1 90); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/login 2>/dev/null | grep -q "200"; then
        echo "✅ Odoo ready!"
        break
    fi
    if [ "$i" -eq 90 ]; then
        echo "⚠️ Odoo not ready yet. Check: docker compose logs odoo"
    fi
    sleep 5
done

# Set ports public
if [ -n "$CODESPACE_NAME" ]; then
    echo "🌐 Setting ports public..."
    gh codespace ports visibility 8069:public 3000:public 8888:public 3100:public -c "$CODESPACE_NAME" 2>/dev/null || true
fi

echo ""
echo "════════════════════════════════════════════"
echo "  NAVI-IMS — Integrated Management System"
echo "════════════════════════════════════════════"
if [ -n "$CODESPACE_NAME" ]; then
echo "  🌐 Odoo:     https://${CODESPACE_NAME}-8069.app.github.dev"
echo "  📱 Soldier:   https://${CODESPACE_NAME}-3000.app.github.dev/patrol/soldier.html"
echo "  📊 Inngest:  https://${CODESPACE_NAME}-8288.app.github.dev"
echo "  📋 Bull:     https://${CODESPACE_NAME}-3100.app.github.dev"
else
echo "  🌐 Odoo:     http://localhost:8069"
echo "  📱 Soldier:   http://localhost:3000/patrol/soldier.html"
fi
echo ""
echo "  Login: admin / admin"
echo "════════════════════════════════════════════"
