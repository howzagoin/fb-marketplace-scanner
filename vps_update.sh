#!/bin/bash
set -e
cd /home/ubuntu/fb-marketplace-scanner
./venv/bin/python -c "from backend.product_analyzer import reconcile_all_excluded_interests; print('VPS Reconcile:', reconcile_all_excluded_interests())"
sudo systemctl restart fb-marketplace.service
sleep 2
systemctl status fb-marketplace.service --no-pager
