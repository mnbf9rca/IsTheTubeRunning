# Frontend Dockerfile for IsTheTubeRunning
# Multi-stage build: Build stage + Production stage with security hardening

# Stage 1: Build
FROM node:24-alpine AS builder

WORKDIR /app

# Copy dependency files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production - Minimal and hardened
FROM busybox:1.36-musl

# Create non-root user
RUN adduser -D -u 1000 -g 1000 -s /sbin/nologin www

# Create web directory with proper permissions
RUN mkdir -p /www && chown -R www:www /www

# Copy built assets from builder stage
COPY --from=builder --chown=www:www /app/dist /www

# Switch to non-root user
USER www

# Expose port 8080 (non-privileged port)
EXPOSE 8080

# Run busybox httpd as non-root with minimal permissions
# -f: foreground, -p: port, -h: home directory, -u: user
CMD ["busybox", "httpd", "-f", "-p", "8080", "-h", "/www"]

# Security labels for container runtime
LABEL security.readonly_rootfs="true" \
      security.no_new_privileges="true" \
      security.drop_all_capabilities="true"
