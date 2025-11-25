#!/bin/bash
# Script to test FastAPI fork safety with multiple uvicorn workers
# Issue #151: Reproduce asyncpg event loop binding issue

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
ENV_FILE="$BACKEND_DIR/.env"
ENV_BACKUP="$BACKEND_DIR/.env.backup.$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FastAPI Fork Safety Test (Issue #151)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to cleanup on exit
# shellcheck disable=SC2329
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"

    # Kill uvicorn if running
    if [ -n "$UVICORN_PID" ]; then
        echo "Stopping uvicorn (PID: $UVICORN_PID)"
        kill "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi

    # Restore .env if backed up
    if [ -f "$ENV_BACKUP" ]; then
        echo "Restoring .env file"
        mv "$ENV_BACKUP" "$ENV_FILE"
    fi

    echo -e "${GREEN}Cleanup complete${NC}"

    # Keep log file for inspection
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}Log file preserved at: $LOG_FILE${NC}"
    fi
}

trap cleanup EXIT INT TERM

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}Error: Backend directory not found at $BACKEND_DIR${NC}"
    exit 1
fi

cd "$BACKEND_DIR"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: .env file not found at $ENV_FILE${NC}"
    exit 1
fi

# Backup .env file
echo -e "${BLUE}1. Backing up .env file${NC}"
cp "$ENV_FILE" "$ENV_BACKUP"

# Set DEBUG=false in .env
echo -e "${BLUE}2. Setting DEBUG=false in .env (enables connection pooling)${NC}"
if grep -q "^DEBUG=" "$ENV_FILE"; then
    # Replace existing DEBUG line
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's/^DEBUG=.*/DEBUG=false/' "$ENV_FILE"
    else
        sed -i 's/^DEBUG=.*/DEBUG=false/' "$ENV_FILE"
    fi
else
    # Add DEBUG line if it doesn't exist
    echo "DEBUG=false" >> "$ENV_FILE"
fi

# Verify DEBUG is set to false
if grep -q "^DEBUG=false" "$ENV_FILE"; then
    echo -e "${GREEN}   ✓ DEBUG=false set${NC}"
else
    echo -e "${RED}   ✗ Failed to set DEBUG=false${NC}"
    exit 1
fi

# Create log file
LOG_FILE="/tmp/uvicorn_fork_test_$$.log"
echo -e "${BLUE}3. Starting uvicorn with 4 workers${NC}"
echo "   Log file: $LOG_FILE"

# Start uvicorn in background with 4 workers
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 > "$LOG_FILE" 2>&1 &
UVICORN_PID=$!

echo "   Uvicorn PID: $UVICORN_PID"

# Wait for uvicorn to start
echo -e "${BLUE}4. Waiting for uvicorn to start...${NC}"
MAX_WAIT=30
WAIT_COUNT=0
while [ "$WAIT_COUNT" -lt "$MAX_WAIT" ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}   ✓ Uvicorn started successfully${NC}"
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    echo -n "."
done

if [ "$WAIT_COUNT" -eq "$MAX_WAIT" ]; then
    echo ""
    echo -e "${RED}   ✗ Uvicorn failed to start within ${MAX_WAIT} seconds${NC}"
    echo -e "${YELLOW}   Last 20 lines of log:${NC}"
    tail -20 "$LOG_FILE"
    exit 1
fi

# Make concurrent requests to trigger the issue
echo ""
echo -e "${BLUE}5. Making concurrent requests to trigger fork safety issue${NC}"
echo "   Sending 50 concurrent requests to database-intensive endpoints..."

# Create a temporary script for concurrent requests
CONCURRENT_SCRIPT="/tmp/concurrent_requests_$$.sh"
cat > "$CONCURRENT_SCRIPT" << 'EOFSCRIPT'
#!/bin/bash
for i in {1..50}; do
    # Try different endpoints that use the database
    curl -s http://localhost:8000/health > /dev/null 2>&1 &
    curl -s http://localhost:8000/docs > /dev/null 2>&1 &
done
wait
EOFSCRIPT
chmod +x "$CONCURRENT_SCRIPT"

# Run concurrent requests
bash "$CONCURRENT_SCRIPT"
rm -f "$CONCURRENT_SCRIPT"

echo -e "${GREEN}   ✓ Requests sent${NC}"

# Wait a bit for any errors to appear in logs
echo -e "${BLUE}6. Waiting for logs (5 seconds)...${NC}"
sleep 5

# Check logs for errors
echo ""
echo -e "${BLUE}7. Checking logs for fork safety errors${NC}"
echo -e "${YELLOW}   Looking for:${NC}"
echo "   - 'Task got Future attached to a different loop'"
echo "   - 'asyncpg.exceptions.*InterfaceError'"
echo "   - 'cannot perform operation: another operation is in progress'"
echo ""

ERRORS_FOUND=false

if grep -i "Task.*got Future.*attached to a different loop" "$LOG_FILE" > /dev/null 2>&1; then
    echo -e "${RED}   ✗ Found event loop error!${NC}"
    grep -i "Task.*got Future.*attached to a different loop" "$LOG_FILE" | head -5
    ERRORS_FOUND=true
fi

if grep -i "asyncpg.*InterfaceError" "$LOG_FILE" > /dev/null 2>&1; then
    echo -e "${RED}   ✗ Found asyncpg InterfaceError!${NC}"
    grep -i "asyncpg.*InterfaceError" "$LOG_FILE" | head -5
    ERRORS_FOUND=true
fi

if grep -i "cannot perform operation.*another operation is in progress" "$LOG_FILE" > /dev/null 2>&1; then
    echo -e "${RED}   ✗ Found asyncpg operation conflict!${NC}"
    grep -i "cannot perform operation.*another operation is in progress" "$LOG_FILE" | head -5
    ERRORS_FOUND=true
fi

# Check for general errors or warnings
ERROR_COUNT=$(grep -i "error" "$LOG_FILE" | grep -c -v "INFO" || echo "0")
WARNING_COUNT=$(grep -c -i "warning" "$LOG_FILE" || echo "0")

echo ""
echo -e "${BLUE}8. Summary${NC}"
echo "   Errors found: $ERROR_COUNT"
echo "   Warnings found: $WARNING_COUNT"

if [ "$ERRORS_FOUND" = true ]; then
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}FORK SAFETY ISSUE DETECTED! ✗${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "The fork safety issue (Issue #151) has been reproduced."
    echo "This confirms that the bug exists when running with multiple workers."
    echo ""
    echo -e "${YELLOW}Full log available at: $LOG_FILE${NC}"
    echo ""
    echo "To view full log:"
    echo "  cat $LOG_FILE"
    echo ""
    echo "To view errors only:"
    echo "  grep -i error $LOG_FILE"
    exit 1
else
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}NO FORK SAFETY ERRORS DETECTED ✓${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}Note: Some errors were found, but they don't appear to be${NC}"
        echo -e "${YELLOW}related to fork safety. Check the log for details.${NC}"
        echo ""
        echo -e "${YELLOW}Recent errors from log:${NC}"
        grep -i "error" "$LOG_FILE" | grep -v "INFO" | tail -10
    else
        echo "Either:"
        echo "  1. The issue has been successfully fixed, OR"
        echo "  2. The issue wasn't triggered by these test requests"
        echo ""
        echo "If this is a before-fix test, try:"
        echo "  - Running the script multiple times"
        echo "  - Increasing the number of concurrent requests"
        echo "  - Testing with authenticated endpoints that hit the database more"
    fi

    echo ""
    echo -e "${YELLOW}Full log available at: $LOG_FILE${NC}"
    exit 0
fi
