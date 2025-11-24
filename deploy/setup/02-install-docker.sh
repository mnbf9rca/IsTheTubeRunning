#!/usr/bin/env bash
# Install Docker Engine and Docker Compose

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== Docker Installation ==="
echo ""

# Check if Docker is already installed
if command_exists docker; then
    DOCKER_VERSION=$(docker --version)
    print_status "Docker is already installed: $DOCKER_VERSION"
    print_info "Skipping Docker installation"
    exit 0
fi

# Install prerequisites
print_info "Installing prerequisites..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
print_info "Adding Docker GPG key..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
print_info "Adding Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package lists
DEBIAN_FRONTEND=noninteractive apt-get update

# Install Docker packages
print_info "Installing Docker Engine and Docker Compose..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Enable and start Docker service
systemctl enable docker
systemctl start docker

# Verify installation
if docker --version && docker compose version; then
    print_status "Docker installed successfully"
    docker --version
    docker compose version
else
    print_error "Docker installation verification failed"
    exit 1
fi

echo ""
print_status "Docker installation complete"
