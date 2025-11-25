#!/usr/bin/env bash
# Clone or update repository
#
# This script:
# 1. Clones the IsTheTubeRunning repository to APP_DIR at specified branch
# 2. If repository already exists, fetches and checks out the specified branch
#
# Prerequisites:
#   - DEPLOYMENT_USER configured in azure-config.json
#   - APP_DIR configured in azure-config.json
#
# Arguments:
#   $1: Git branch to clone/checkout (required, no default)

set -euo pipefail

# Validate branch argument
if [ $# -ne 1 ]; then
    echo "ERROR: Branch argument required" >&2
    echo "Usage: $0 <branch>" >&2
    echo "Example: $0 main" >&2
    exit 1
fi

GIT_BRANCH="$1"

# Source common functions and Azure config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

# Declare required configuration
validate_required_config "DEPLOYMENT_USER" "APP_DIR" || exit 1

require_root

echo "=== Repository Clone/Update ==="
echo ""

# Check if repository directory exists
if [ -d "$APP_DIR" ] && [ "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
    print_status "Repository directory already exists: $APP_DIR"
    print_info "Updating to branch: $GIT_BRANCH"
    echo ""

    # Fetch latest changes from origin (show output for debugging)
    print_info "Fetching latest changes from origin..."
    if sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" fetch origin; then
        print_status "Fetched latest changes from origin"
    else
        print_error "Failed to fetch from origin"
        exit 1
    fi
    echo ""

    # Checkout the requested branch (will track remote if not local)
    print_info "Checking out branch: $GIT_BRANCH"
    if sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" checkout "$GIT_BRANCH"; then
        print_status "Checked out branch: $GIT_BRANCH"
    else
        echo ""
        print_error "Failed to checkout branch: $GIT_BRANCH"
        print_info "Branch may not exist on remote. Available remote branches:"
        sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" branch -r | grep -v HEAD
        echo ""
        print_info "Push the branch to GitHub first:"
        print_info "  git push origin $GIT_BRANCH"
        exit 1
    fi
    echo ""

    # Pull latest changes for this branch
    print_info "Pulling latest changes for $GIT_BRANCH..."
    if sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" pull origin "$GIT_BRANCH"; then
        print_status "Repository updated to latest $GIT_BRANCH"
    else
        print_error "Failed to pull latest changes"
        exit 1
    fi
else
    print_info "Cloning repository to $APP_DIR (branch: $GIT_BRANCH)..."
    echo ""

    # Create parent directory if it doesn't exist
    mkdir -p "$(dirname "$APP_DIR")"

    # Clone as deployment user with specific branch (show output for debugging)
    if sudo -u "$DEPLOYMENT_USER" git clone --branch "$GIT_BRANCH" https://github.com/mnbf9rca/IsTheTubeRunning.git "$APP_DIR"; then
        print_status "Repository cloned successfully (branch: $GIT_BRANCH)"
    else
        echo ""
        print_error "Failed to clone branch: $GIT_BRANCH"
        print_info "Branch may not exist on remote"
        print_info "Push the branch to GitHub first:"
        print_info "  git push origin $GIT_BRANCH"
        exit 1
    fi
fi

echo ""
print_status "Repository clone/update complete"
print_info "Repository is at: $APP_DIR"
print_info "Branch: $GIT_BRANCH"
