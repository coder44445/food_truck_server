# Dockerfile
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# The production command is typically set by Gunicorn/Uvicorn in Docker Compose
# Default command for development (can be overridden by docker-compose.yml)
# CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app.main:app"]
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker","-b", "0.0.0.0:8000", "app.main:app"]