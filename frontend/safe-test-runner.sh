#!/bin/bash

# Safe Test Runner with Process Monitoring
# This script runs tests with strict timeouts and monitors for runaway processes

set -e

FRONTEND_DIR="/Users/rob/Downloads/git/IsTheTubeRunning/frontend"
TIMEOUT_SECONDS=60
LOG_FILE="$FRONTEND_DIR/test-diagnostics.log"

echo "=== Safe Test Runner ===" | tee "$LOG_FILE"
echo "Started at: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Function to get current node processes
get_node_processes() {
    # shellcheck disable=SC2009
    ps aux | grep -E "(node|vitest|vite)" | grep -v grep | grep -v "safe-test-runner" || true
}

# Function to cleanup processes
# shellcheck disable=SC2329
cleanup() {
    echo "" | tee -a "$LOG_FILE"
    echo "=== CLEANUP TRIGGERED ===" | tee -a "$LOG_FILE"
    echo "Timestamp: $(date)" | tee -a "$LOG_FILE"

    # Kill the test process tree if it's still running
    if [ -n "$TEST_PID" ] && kill -0 "$TEST_PID" 2>/dev/null; then
        echo "Killing test process $TEST_PID and its children" | tee -a "$LOG_FILE"
        # Kill all child processes first
        pkill -9 -P "$TEST_PID" 2>/dev/null || true
        # Then kill the main process
        kill -9 "$TEST_PID" 2>/dev/null || true
    fi

    # Kill any remaining vitest processes (specific to tests)
    pkill -9 -f "vitest" 2>/dev/null || true

    echo "Cleanup complete" | tee -a "$LOG_FILE"
}

# Set trap to cleanup on exit or interrupt
trap cleanup EXIT INT TERM

# Capture baseline processes
echo "=== Baseline Node Processes ===" | tee -a "$LOG_FILE"
BASELINE=$(get_node_processes)
echo "$BASELINE" | tee -a "$LOG_FILE"
BASELINE_COUNT=$(echo "$BASELINE" | grep -c -v "^$" || echo "0")
echo "Baseline process count: $BASELINE_COUNT" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Change to frontend directory
cd "$FRONTEND_DIR"

# Run tests with timeout and capture PID
echo "=== Running Tests ===" | tee -a "$LOG_FILE"
echo "Timeout: ${TIMEOUT_SECONDS}s" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Run tests in background and monitor
timeout ${TIMEOUT_SECONDS}s npm run test:run > test-output.log 2>&1 &
TEST_PID=$!

echo "Test process PID: $TEST_PID" | tee -a "$LOG_FILE"

# Monitor process count every 2 seconds
MONITOR_COUNT=0
MAX_MONITORS=30

while kill -0 "$TEST_PID" 2>/dev/null; do
    sleep 2
    MONITOR_COUNT=$((MONITOR_COUNT + 1))

    CURRENT=$(get_node_processes)
    CURRENT_COUNT=$(echo "$CURRENT" | grep -c -v "^$" || echo "0")
    DIFF=$((CURRENT_COUNT - BASELINE_COUNT))

    echo "[Monitor $MONITOR_COUNT] Process count: $CURRENT_COUNT (baseline: $BASELINE_COUNT, diff: +$DIFF)" | tee -a "$LOG_FILE"

    # Allow initial worker spawn (Vitest creates ~10 workers), but watch for runaway growth
    # After first check, if we see more than 20 processes, something is leaking
    if [ "$MONITOR_COUNT" -gt 3 ] && [ "$DIFF" -gt 20 ]; then
        echo "!!! WARNING: Process leak detected ($DIFF new processes) !!!" | tee -a "$LOG_FILE"
        echo "=== New Processes ===" | tee -a "$LOG_FILE"
        echo "$CURRENT" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        echo "Killing test process..." | tee -a "$LOG_FILE"
        kill -9 "$TEST_PID" 2>/dev/null || true
        break
    fi

    # Safety check - don't monitor forever
    if [ "$MONITOR_COUNT" -ge "$MAX_MONITORS" ]; then
        echo "!!! WARNING: Monitoring timeout reached !!!" | tee -a "$LOG_FILE"
        kill -9 "$TEST_PID" 2>/dev/null || true
        break
    fi
done

# Wait for test process to finish
wait "$TEST_PID" 2>/dev/null
TEST_EXIT_CODE=$?

echo "" | tee -a "$LOG_FILE"
echo "=== Test Execution Complete ===" | tee -a "$LOG_FILE"
echo "Exit code: $TEST_EXIT_CODE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Capture final process state
echo "=== Final Node Processes ===" | tee -a "$LOG_FILE"
FINAL=$(get_node_processes)
echo "$FINAL" | tee -a "$LOG_FILE"
FINAL_COUNT=$(echo "$FINAL" | grep -c -v "^$" || echo "0")
echo "Final process count: $FINAL_COUNT" | tee -a "$LOG_FILE"
echo "Difference: +$((FINAL_COUNT - BASELINE_COUNT))" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Show test output
echo "=== Test Output (last 50 lines) ===" | tee -a "$LOG_FILE"
tail -50 test-output.log | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Completed at: $(date)" | tee -a "$LOG_FILE"
echo "Full logs saved to: $LOG_FILE"
echo "Test output saved to: $FRONTEND_DIR/test-output.log"

# Check if we have leaked processes
LEAKED=$((FINAL_COUNT - BASELINE_COUNT))
if [ "$LEAKED" -gt 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "!!! WARNING: $LEAKED process(es) leaked !!!" | tee -a "$LOG_FILE"
    exit 1
fi

exit $TEST_EXIT_CODE
