# Deployment Guide

## Local Deployment
Use the local setup instructions in [installation.md](installation.md) to run the app on a development machine.

## Docker Deployment
The repository includes Docker files for containerized deployment.

```powershell
docker compose build
docker compose up -d
```

Run database migrations inside the container:
```powershell
docker compose exec web flask db upgrade
```

## Render / Cloud Deployment
The project includes deployment configuration through [render.yaml](../render.yaml) and [Procfile](../Procfile).

Recommended deployment steps:
1. Push the project to a private GitHub repository.
2. Create a Render service from the repository.
3. Configure environment variables such as `DATABASE_URL` and `GROQ_API_KEY`.
4. Ensure the health endpoint at `/healthz` is reachable.

## Production Considerations
- Use a strong `SECRET_KEY`.
- Use a managed PostgreSQL database.
- Keep `.env` out of source control.
- Monitor logs and database connectivity.
- Use a health monitor for free-tier hosting to prevent idle shutdowns.
