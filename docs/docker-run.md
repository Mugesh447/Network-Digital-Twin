# Docker Build and Run Guide

## Prerequisites

- Docker Desktop running
- Repository root as the current directory
- A copy of `backend/.env.example` named `.env` when SMTP or GNS3 integration is required

## 1. Prepare Environment Variables

PowerShell:

```powershell
Copy-Item backend\.env.example .env
```

Edit `.env` and set only the integrations you use. Never commit real passwords, app passwords, or tokens.

## 2. Build the Image

Run from the repository root, where the `Dockerfile` is located:

```powershell
docker build -t network-digital-twin:latest .
```

The Dockerfile installs `backend/requirements.txt`, copies the backend and frontend, and exposes port `5000`.

## 3. Run the Container

```powershell
docker run --name network-digital-twin --rm `
  -p 5000:5000 `
  --env-file .env `
  network-digital-twin:latest
```

Open:

```text
http://localhost:5000
```

Health check:

```powershell
Invoke-RestMethod http://localhost:5000/health
```

Prometheus metrics:

```text
http://localhost:5000/metrics
```

Stop the container with `Ctrl+C`.

## 4. SMTP Email Alerts

Set these variables in `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=provider-app-password
SMTP_FROM=alerts@example.com
ALERT_EMAIL_TO=network-team@example.com
```

Then sign in as an Admin and use **Advanced > Send email alert**. The API is:

```text
POST /api/alerts/email
```

For Gmail or Microsoft 365, use an app password or approved SMTP credential. Do not use a normal account password in `.env`.

## 5. GNS3 Live Sync

If GNS3 is running on the host machine, use `host.docker.internal` from inside Docker Desktop:

```env
GNS3_SERVER_URL=http://host.docker.internal:3080
GNS3_PROJECT_ID=your-existing-project-id
GNS3_AUTH_TOKEN=
```

Then sign in as an Admin and run **Advanced > GNS3 Sync**. The API is:

```text
POST /api/gns3/sync
```

The configured GNS3 project must already exist. Without `GNS3_SERVER_URL` and `GNS3_PROJECT_ID`, the endpoint returns a preview and does not call an external server.

## 6. Local Development Without Docker

```powershell
python app.py
```

The root launcher starts the backend and serves the separate `frontend/` folder.

## Security Notes

- Keep `.env` out of Git; the repository `.gitignore` should include it before publishing.
- Use a private container registry for production images.
- The included Flask server is intended for development/demo use. Use a production WSGI server and HTTPS before public deployment.
