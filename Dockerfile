# Stage 1: Build frontend
FROM node:18-alpine as frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/public ./public
COPY frontend/src ./src

# Accept build arguments from environment
ARG REACT_APP_AUTH_USER_PW=password
ARG REACT_APP_AUTH_ADMIN_PW=password
ARG REACT_APP_AUTH_SUPERUSER_PW=password
ARG REACT_APP_VIDEO_PLAYER_PACKAGE=

# Set environment variables for React build
ENV REACT_APP_AUTH_USER_PW=${REACT_APP_AUTH_USER_PW}
ENV REACT_APP_AUTH_ADMIN_PW=${REACT_APP_AUTH_ADMIN_PW}
ENV REACT_APP_AUTH_SUPERUSER_PW=${REACT_APP_AUTH_SUPERUSER_PW}
ENV REACT_APP_VIDEO_PLAYER_PACKAGE=${REACT_APP_VIDEO_PLAYER_PACKAGE}

RUN npm run build

# Stage 2: Build backend
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies: adb, ffmpeg (includes ffprobe), and a font for LoadScreen generation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        android-tools-adb \
        ffmpeg \
        fonts-dejavu-core \
        curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /carestream

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY run.py .
COPY entrypoint.sh .
RUN chmod +x /carestream/entrypoint.sh

# Copy built frontend from Stage 1
COPY --from=frontend-builder /frontend/build ./app/static

# Create directories for media and data
RUN mkdir -p /carestream/media /carestream/data

EXPOSE ${CARESTREAM_PORT:-8000}

# Start with gunicorn + eventlet for production WebSocket support
ENTRYPOINT ["/carestream/entrypoint.sh"]
