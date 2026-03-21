#!/bin/bash
# ═══ First-time setup (postCreateCommand) ═══
set -e

echo "🚀 NAVI-IMS — Setting up Codespace..."

# Install docker CLI (needed for docker compose commands in start.sh)
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker CLI..."
    curl -fsSL https://get.docker.com | sh 2>/dev/null || true
fi

# Copy .env if not exists
if [ ! -f /workspace/.env ]; then
    cp /workspace/.env.example /workspace/.env 2>/dev/null || cat > /workspace/.env << 'EOF'
POSTGRES_USER=odoo
POSTGRES_PASSWORD=odoo_secret_2026
POSTGRES_DB=odoo
INNGEST_EVENT_KEY=abc123def456
INNGEST_SIGNING_KEY=signkey-test-abc123def456abc123def456
INNGEST_POSTGRES_URI=postgres://inngest:inngest_secret@postgres-inngest:5432/inngest
REDIS_URL=redis://redis:6379/0
ODOO_URL=http://odoo:8069
EOF
    echo "✅ .env created"
fi

echo "✅ Setup complete!"
