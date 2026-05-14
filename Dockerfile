# Stage 1: Build Next.js static frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy backend source and install dependencies
COPY backend/pyproject.toml ./
RUN uv sync --no-dev

# Copy backend code
COPY backend/main.py ./

# Copy built frontend static files
COPY --from=frontend-builder /app/frontend/out ./frontend_out

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
