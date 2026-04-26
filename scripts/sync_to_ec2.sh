#!/usr/bin/env bash
# sync_to_ec2.sh — Push mutable data files to EC2
# Usage: ./scripts/sync_to_ec2.sh
#
# EC2-authoritative files (edit on EC2, pull locally if needed):
#   promo_proverbs.json  — proverbs grow on EC2 via Discord bot
#
# Local-authoritative files (edit locally, push to EC2):
#   promo_leads.json     — leads managed from local dashboard
#   promo_contacts.json  — contacts managed from local dashboard
#   promo_proverbs.json  — also push local library additions to EC2

set -euo pipefail

EC2_IP="13.218.60.13"
EC2_USER="ubuntu"
KEY="$HOME/Indaba/ec2-key.pem"
EC2_DATA="/opt/indaba-app/data"
LOCAL_DATA="$(dirname "$0")/../data"

FILES=(
    "promo_leads.json"
    "promo_contacts.json"
    "promo_proverbs.json"
)

echo "Syncing data files to EC2 ($EC2_IP)..."
for FILE in "${FILES[@]}"; do
    LOCAL="$LOCAL_DATA/$FILE"
    if [ -f "$LOCAL" ]; then
        scp -i "$KEY" -q "$LOCAL" "$EC2_USER@$EC2_IP:$EC2_DATA/$FILE"
        echo "  ✓ $FILE"
    else
        echo "  ⚠ $FILE not found locally, skipping"
    fi
done

echo "Done. Restart indaba-app if needed:"
echo "  ssh -i $KEY $EC2_USER@$EC2_IP 'sudo systemctl restart indaba-app'"
