#!/usr/bin/env bash
# Azure Configuration for IsTheTubeRunning Deployment
# This file contains centralized Azure configuration settings.
# Source this file in other scripts: source "$(dirname "$0")/azure-config.sh"

# Azure Subscription and Resource Group
# Override with environment variables if needed
export AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
export AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-isthetube-prod}"
export AZURE_LOCATION="${AZURE_LOCATION:-uksouth}"

# Virtual Machine Configuration
export AZURE_VM_NAME="${AZURE_VM_NAME:-isthetube-vm}"
export AZURE_VM_SIZE="${AZURE_VM_SIZE:-Standard_D2s_v3}"  # 2 vCPU, 8GB RAM
export AZURE_VM_IMAGE="${AZURE_VM_IMAGE:-Canonical:ubuntu-24_04-lts:server:latest}"
export AZURE_VM_OS_DISK_SIZE="${AZURE_VM_OS_DISK_SIZE:-128}"  # GB

# Network Configuration
export AZURE_VNET_NAME="${AZURE_VNET_NAME:-isthetube-vnet}"
export AZURE_SUBNET_NAME="${AZURE_SUBNET_NAME:-isthetube-subnet}"
export AZURE_NSG_NAME="${AZURE_NSG_NAME:-isthetube-nsg}"
export AZURE_PUBLIC_IP_NAME="${AZURE_PUBLIC_IP_NAME:-isthetube-ip}"

# Storage Configuration (for backups)
export AZURE_STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-isthetubestorage}"
export AZURE_STORAGE_CONTAINER="${AZURE_STORAGE_CONTAINER:-backups}"

# SSH Configuration
export AZURE_SSH_KEY_NAME="${AZURE_SSH_KEY_NAME:-isthetube-deploy-key}"
export AZURE_ADMIN_USERNAME="${AZURE_ADMIN_USERNAME:-azureuser}"

# Deployment Configuration
export DEPLOYMENT_USER="${DEPLOYMENT_USER:-deployuser}"
export APP_DIR="${APP_DIR:-/opt/isthetube}"

# Domain Configuration
export DOMAIN_NAME="${DOMAIN_NAME:-isthetube.cynexia.com}"
