# Frontend Dockerfile for IsTheTubeRunning
# Multi-stage build: Build stage + Production stage with security hardening

# Stage 1: Build
FROM node:24-alpine AS builder

WORKDIR /app

# Copy dependency files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --include dev --include optional

# Copy source code
COPY . .

# Accept build commit hash as build arg (defaults to "unknown" for local builds)
ARG BUILD_COMMIT=unknown
ENV VITE_BUILD_COMMIT=${BUILD_COMMIT}

# Build the application (no environment-specific config - loaded at runtime)
RUN npm run build

# Stage 2: Production - Minimal and hardened
FROM busybox:1.36-musl

# Create non-root user
RUN adduser -D -u 1000 -g 1000 -s /sbin/nologin www

# Copy built assets from builder stage to staging directory
# Files are copied from /www-build to /www at runtime to ensure fresh deployments
COPY --from=builder --chown=www:www /app/dist /www-build

# Create runtime directory (volume mount point in production)
RUN mkdir -p /www && chown www:www /www

# Switch to non-root user
USER www

# Expose port 8080 (non-privileged port)
EXPOSE 8080

# Copy assets from staging to runtime dir, then serve (removes stale files on each start)
# Production: command is overridden in docker-compose to just copy and exit
# Standalone/test: copies then runs httpd
CMD ["sh", "-c", "rm -rf /www/* && cp -a /www-build/. /www/ && busybox httpd -f -p 8080 -h /www"]

# Security labels for container runtime
LABEL security.readonly_rootfs="true" \
      security.no_new_privileges="true" \
      security.drop_all_capabilities="true"
