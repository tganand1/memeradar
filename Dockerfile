FROM python:3.11-slim AS backend-build
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*

COPY --from=backend-build /app/backend /app/backend
COPY --from=frontend-build /app/frontend /app/frontend
COPY --from=frontend-build /app/frontend/.next /app/frontend/.next

WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000 3000
CMD ["python", "run.py"]
