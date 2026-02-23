FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY . .

# Create data directories
RUN mkdir -p /data/tasks/available /data/tasks/claimed \
             /data/tasks/completed /data/tasks/failed \
             /data/memory /data/audit

ENV PYTHONPATH=/app
ENV HOME=/data
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
