# Deployment Guide (DEPLOY.md)

## Requirements
- Docker and Docker Compose (recommended)
- Python 3.11+ & Node.js 20+ (for manual deployment)
- Helius API Key (Mainnet RPC + WebSocket)
- RugCheck API Key (optional)
- Telegram Bot Token & Chat ID (optional)

## Configuration
All environment variables are stored in `backend/.env`. Never commit `.env` to version control.

Sample `.env`:
```env
HELIUS_API_KEY=your_helius_key_here
RUGCHECK_API_KEY=your_rugcheck_key_here
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
MEMERADAR_MODE=live
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=your_secure_password_here
```

## Running with Docker Compose

1. Ensure `backend/.env` is configured.
2. Build and start containers with automatic restart and persistent volume storage:
   ```bash
   docker-compose up --build -d
   ```
3. Access the dashboard at `http://localhost:3000` (Caddy is the public entry point on port 3000). If `DASHBOARD_PASSWORD` is set, enter the password to authenticate.

## Services

### Caddy (port 3000)
- Public entry point, routes based on path
- `/api/*` and `/ws*` → backend container on port 8000
- Everything else → frontend container on port 3000
- Handles dashboard password authentication
- WebSocket connections through `/ws*` are proxied to the backend

### memeradar (backend + frontend)
- No ports published to the host
- Communicates internally via Docker network
- Backend API and WebSocket available only through Caddy

## Database & Persistence

- Live database is stored at `backend/data/memeradar_live.db`
- Docker Compose persists data using the `memeradar_data` volume attached to `/app/backend/data`
- Database survives container restarts due to volume mounting
- The separate `memeradar_db` volume has been removed (was unused)

## SSL (Production)
For production with a real domain, place your domain in the Caddyfile and Caddy will automatically provision HTTPS using Let's Encrypt. The dashboard password authentication still applies.