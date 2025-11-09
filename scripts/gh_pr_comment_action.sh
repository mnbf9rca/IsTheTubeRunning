#!/usr/bin/env bash
#
# gh_pr_comment_action.sh
# Wrapper script for GitHub CLI to manage PR review comments and threads
#
# Usage:
#   gh_pr_comment_action.sh <pr_number> <comment_or_thread_id> <action> <response_text>
#
# Arguments:
#   pr_number           - Pull request number
#   comment_or_thread_id - Comment ID (numeric) or Thread ID (PRT_xxx format)
#   action              - Action to perform: respond | resolve | reject | in-progress
#   response_text       - Response text (required for all actions)
#
# Actions:
#   respond     - Post a reply to a review comment
#   resolve     - Mark a review thread as resolved (posts response then resolves)
#   reject      - Post a comment marking the thread as rejected
#   in-progress - Post a comment marking the thread as in-progress
#
# Environment:
#   GITHUB_TOKEN or gh authentication must be configured
#
# Output:
#   JSON-formatted result for agent consumption
#

set -euo pipefail

# Early dependency check - jq is required for safe JSON construction
if ! command -v jq &> /dev/null; then
    echo '{"status":"error","message":"jq is required but not installed"}' >&2
    exit 1
fi

# Output functions for structured logging (using jq for safe JSON construction)
log_error() {
    jq -nc --arg msg "$1" '{status: "error", message: $msg}' >&2
}

log_success() {
    jq -nc --arg msg "$1" --argjson data "$2" '{status: "success", message: $msg, data: $data}'
}

# Get owner and repo from git remote
get_repo_info() {
    local remote_url
    remote_url=$(git config --get remote.origin.url 2>/dev/null || echo "")

    if [[ -z "$remote_url" ]]; then
        log_error "Could not determine repository from git remote"
        exit 1
    fi

    # Parse GitHub URL (supports both HTTPS and SSH)
    if [[ "$remote_url" =~ github.com[:/]([^/]+)/([^/.]+) ]]; then
        REPO_OWNER="${BASH_REMATCH[1]}"
        REPO_NAME="${BASH_REMATCH[2]}"
    else
        log_error "Could not parse GitHub repository from remote URL: $remote_url"
        exit 1
    fi
}

# Check if gh CLI is installed and authenticated
check_gh_auth() {
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) is not installed"
        exit 1
    fi

    if ! gh auth status > /dev/null 2>&1; then
        log_error "GitHub CLI not authenticated. Run 'gh auth login'"
        exit 1
    fi
}

# Convert comment ID to thread ID using GraphQL
get_thread_id_from_comment() {
    local pr_number="$1"
    local comment_id="$2"

    local query='query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          comments(first: 100) {
            nodes {
              databaseId
              id
            }
          }
        }
      }
    }
  }
}'

    local response
    response=$(gh api graphql \
        -f query="$query" \
        -f owner="$REPO_OWNER" \
        -f repo="$REPO_NAME" \
        -F pr="$pr_number")
    local gh_status=$?

    # Check for errors from gh api command
    if [[ $gh_status -ne 0 ]]; then
        log_error "gh api command failed with exit code $gh_status"
        exit 1
    fi

    # Check for GraphQL errors
    if echo "$response" | jq -e '.errors' > /dev/null 2>&1; then
        local error_msg
        error_msg=$(echo "$response" | jq -r '.errors[0].message // "Unknown GraphQL error"')
        log_error "Failed to fetch review threads: $error_msg"
        exit 1
    fi

    # Find thread containing the comment
    local thread_id
    thread_id=$(echo "$response" | jq -r --arg cid "$comment_id" '
        .data.repository.pullRequest.reviewThreads.nodes[]
        | select(.comments.nodes[].databaseId == ($cid | tonumber))
        | .id
    ' | head -n 1)

    if [[ -z "$thread_id" ]]; then
        log_error "Could not find thread ID for comment ID: $comment_id"
        exit 1
    fi

    echo "$thread_id"
}

# Internal function to post a reply without output (returns comment ID on stdout)
_post_reply() {
    local pr_number="$1"
    local comment_id="$2"
    local response_text="$3"

    local response
    response=$(gh api \
        --method POST \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/repos/$REPO_OWNER/$REPO_NAME/pulls/$pr_number/comments/$comment_id/replies" \
        -f body="$response_text")
    local gh_status=$?

    # Check for errors from gh api command
    if [[ $gh_status -ne 0 ]]; then
        log_error "gh api command failed with exit code $gh_status"
        exit 1
    fi

    # Check for errors in API response
    if echo "$response" | jq -e '.message' > /dev/null 2>&1; then
        local error_msg
        error_msg=$(echo "$response" | jq -r '.message // "Unknown error"')
        log_error "Failed to post reply: $error_msg"
        exit 1
    fi

    # Extract and return new comment ID
    local new_comment_id
    new_comment_id=$(echo "$response" | jq -r '.id // empty')

    if [[ -z "$new_comment_id" ]]; then
        log_error "Failed to extract comment ID from response"
        exit 1
    fi

    echo "$new_comment_id"
}

# Post a reply to a review comment
action_respond() {
    local pr_number="$1"
    local comment_id="$2"
    local response_text="$3"

    # Call internal function to post reply
    local new_comment_id
    new_comment_id=$(_post_reply "$pr_number" "$comment_id" "$response_text")

    # Output success with safely constructed JSON
    local data_json
    data_json=$(jq -n --arg cid "$new_comment_id" '{comment_id: $cid}')
    log_success "Reply posted successfully" "$data_json"
}

# Resolve a review thread
action_resolve() {
    local pr_number="$1"
    local id="$2"
    local response_text="$3"

    local comment_id
    local thread_id

    # Check if ID is numeric (comment ID) or thread ID
    if [[ "$id" =~ ^[0-9]+$ ]]; then
        # It's a comment ID - convert to thread ID first
        comment_id="$id"
        thread_id=$(get_thread_id_from_comment "$pr_number" "$comment_id")
    else
        # It's a thread ID - we cannot post a reply without a comment ID
        log_error "Resolve action requires a numeric comment ID, not a thread ID: $id"
        exit 1
    fi

    # Post the response comment using comment ID (suppress output, we'll output once at the end)
    _post_reply "$pr_number" "$comment_id" "$response_text" > /dev/null

    local mutation='mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread {
      id
      isResolved
    }
  }
}'

    local response
    response=$(gh api graphql \
        -f query="$mutation" \
        -f threadId="$thread_id")
    local gh_status=$?

    # Check for errors from gh api command
    if [[ $gh_status -ne 0 ]]; then
        log_error "gh api command failed with exit code $gh_status"
        exit 1
    fi

    # Check for GraphQL errors
    if echo "$response" | jq -e '.errors' > /dev/null 2>&1; then
        local error_msg
        error_msg=$(echo "$response" | jq -r '.errors[0].message // "Unknown GraphQL error"')
        log_error "Failed to resolve thread: $error_msg"
        exit 1
    fi

    # Verify resolution
    local is_resolved
    is_resolved=$(echo "$response" | jq -r '.data.resolveReviewThread.thread.isResolved // false')

    if [[ "$is_resolved" == "true" ]]; then
        # Use jq to safely construct JSON output
        local data_json
        data_json=$(jq -n --arg tid "$thread_id" '{thread_id: $tid, is_resolved: true}')
        log_success "Thread resolved successfully" "$data_json"
    else
        log_error "Thread resolution failed"
        exit 1
    fi
}

# Post a comment marking thread as rejected
action_reject() {
    local pr_number="$1"
    local comment_id="$2"
    local response_text="$3"

    # Use respond action to post the rejection comment
    action_respond "$pr_number" "$comment_id" "$response_text"
}

# Post a comment marking thread as in-progress
action_in_progress() {
    local pr_number="$1"
    local comment_id="$2"
    local response_text="$3"

    # Use respond action to post the in-progress comment
    action_respond "$pr_number" "$comment_id" "$response_text"
}

# Display usage information
usage() {
    cat << EOF
Usage: $0 <pr_number> <comment_or_thread_id> <action> <response_text>

Arguments:
  pr_number           Pull request number
  comment_or_thread_id Comment ID (numeric) or Thread ID (PRT_xxx format)
  action              Action to perform: respond | resolve | reject | in-progress
  response_text       Response text (required for all actions)

Actions:
  respond     Post a reply to a review comment
  resolve     Post a response and mark review thread as resolved (auto-converts comment ID to thread ID)
  reject      Post a comment marking the thread as rejected
  in-progress Post a comment marking the thread as in-progress

Examples:
  # Reply to a comment
  $0 123 456789 respond "Fixed in commit abc123"

  # Resolve a thread by comment ID
  $0 123 456789 resolve "Addressed in latest commit"

  # Mark as rejected
  $0 123 456789 reject "Not applicable for this PR"

  # Mark as in-progress
  $0 123 456789 in-progress "Working on this now"

Environment:
  GITHUB_TOKEN or gh authentication must be configured

Output:
  JSON-formatted result for agent consumption
EOF
    exit 1
}

# Main function
main() {
    # Parse arguments
    if [[ $# -lt 4 ]]; then
        usage
    fi

    local pr_number="$1"
    local comment_or_thread_id="$2"
    local action="$3"
    local response_text="${4:-}"

    # Validate PR number
    if [[ ! "$pr_number" =~ ^[0-9]+$ ]]; then
        log_error "PR number must be numeric: $pr_number"
        exit 1
    fi

    # Validate action
    case "$action" in
        respond|resolve|reject|in-progress)
            ;;
        *)
            log_error "Invalid action: $action. Must be one of: respond, resolve, reject, in-progress"
            exit 1
            ;;
    esac

    # Validate response text is provided
    if [[ -z "$response_text" ]]; then
        log_error "Response text is required for action: $action"
        exit 1
    fi

    # Check prerequisites
    check_gh_auth
    get_repo_info

    # Execute action
    case "$action" in
        respond)
            action_respond "$pr_number" "$comment_or_thread_id" "$response_text"
            ;;
        resolve)
            action_resolve "$pr_number" "$comment_or_thread_id" "$response_text"
            ;;
        reject)
            action_reject "$pr_number" "$comment_or_thread_id" "$response_text"
            ;;
        in-progress)
            action_in_progress "$pr_number" "$comment_or_thread_id" "$response_text"
            ;;
    esac
}

# Run main function
main "$@"
