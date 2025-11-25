#!/bin/bash
# Test runner script to avoid consent prompts
# Usage: ./test-runner.sh [test-file-pattern] [additional-args]

cd "$(dirname "$0")" || exit

if [ -z "$1" ]; then
  # No arguments - run all tests
  npm test -- --run
else
  # Run specific test pattern
  npm test -- "$@" --run
fi
