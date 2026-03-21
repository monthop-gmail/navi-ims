#!/bin/bash
# ═══ First-time setup (postCreateCommand) ═══

echo "🚀 NAVI-IMS — Setting up Codespace..."

# Install docker CLI if not available
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker CLI..."
    sudo apt-get update -qq && sudo apt-get install -y -qq docker.io 2>/dev/null || \
    curl -fsSL https://get.docker.com | sh 2>/dev/null || true
fi

# Verify docker works
if docker ps &>/dev/null; then
    echo "✅ Docker CLI ready"
else
    echo "⚠️ Docker CLI not working — may need docker socket mount"
fi

# Copy .env if not exists
if [ ! -f /workspace/.env ]; then
    if [ -f /workspace/.env.example ]; then
        cp /workspace/.env.example /workspace/.env
    else
        cat > /workspace/.env << 'ENVEOF'
POSTGRES_USER=odoo
POSTGRES_PASSWORD=odoo_secret_2026
POSTGRES_DB=odoo
INNGEST_EVENT_KEY=abc123def456
INNGEST_SIGNING_KEY=signkey-test-abc123def456abc123def456
INNGEST_POSTGRES_URI=postgres://inngest:inngest_secret@postgres-inngest:5432/inngest
REDIS_URL=redis://redis:6379/0
ODOO_URL=http://odoo:8069
ENVEOF
    fi
    echo "✅ .env created"
fi

echo "✅ Setup complete — start.sh will run next"
