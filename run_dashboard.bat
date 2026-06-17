@echo off
echo =======================================================
echo          STARTING IIIS FOUNDER INTELLIGENCE DASHBOARD
echo =======================================================
set ADMIN_EMAIL=admin@iiis.com
set ADMIN_PASSWORD=strong_password_here
rem Set SLACK_WEBHOOK_URL in your environment or .env file before running
rem set SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_REAL_WEBHOOK_HERE
py dashboard_server.py
pause
