# Base Python Image
FROM python:3.10-slim

# Metadatos
LABEL maintainer="n8n Architect MCP"
LABEL description="God Level MCP Server for n8n"

# Prevent Python pyc files and buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies if required (mostly for healthchecks found in some setups, curl etc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run as non-root user for security (optional, but good practice. 
# HOWEVER, access to docker.sock might require root or specific group. 
# Keeping root for now to ensure docker socket access works easily on most setups)
# user mcp
# RUN adduser --disabled-password --gecos '' mcp
# USER mcp

# Command to run
CMD ["python", "run.py"]
