#!/usr/bin/env bash
#
# gh_pr_comment_action.sh
# Wrapper script for GitHub CLI to manage PR review comments and threads
#
# Usage:
#   gh_pr_comment_action.sh <pr_number> <id> <response_text>
#
# Arguments:
#   pr_number           - Pull request number
#   id                  - Comment ID, Thread ID, or Comment Node ID:
#                         - Numeric comment database ID (e.g., 2566690774)
#                         - Thread node ID (e.g., PRRT_kwDOQNO0Es5jvUvj)
#                         - Comment node ID (e.g., PRRC_kwDOQNO0Es6Y_JfW)
#   response_text       - Response text (required)
#
# Behavior:
#   Posts a reply to the comment/thread, then marks the review thread as resolved
#
# Environment:
#   GITHUB_TOKEN or gh authentication must be configured
#
# Output:
#   JSON-formatted result for agent consumption
#
# Limitations:
#   - Thread ID lookup queries first 100 review threads and first 100 comments per thread
#   - For PRs with >100 threads or threads with >100 comments, lookup may fail
#   - Consider providing thread ID directly if comment ID lookup fails
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

    # shellcheck disable=SC2016
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

# Post a reply to a review comment using REST API
post_reply_rest() {
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

    # Extract new comment ID (check for success by verifying expected field exists)
    local new_comment_id
    new_comment_id=$(echo "$response" | jq -r '.id // empty')

    # If no ID in response, it's an error - extract error message if available
    if [[ -z "$new_comment_id" ]]; then
        local error_msg
        error_msg=$(echo "$response" | jq -r '.message // "Unknown error: response missing expected .id field"')
        log_error "Failed to post reply: $error_msg"
        exit 1
    fi
}

# Post a reply to a review thread using GraphQL
post_reply_graphql() {
    local thread_id="$1"
    local response_text="$2"

    # Safely encode variables as JSON to prevent injection
    local thread_id_json
    thread_id_json=$(echo "$thread_id" | jq -Rs '.')
    local body_json
    body_json=$(echo "$response_text" | jq -Rs '.')

    local response
    response=$(cat << EOF | gh api graphql --input -
{
  "query": "mutation(\$threadId: ID!, \$body: String!) { addPullRequestReviewThreadReply(input: { pullRequestReviewThreadId: \$threadId, body: \$body }) { comment { id } } }",
  "variables": { "threadId": $thread_id_json, "body": $body_json }
}
EOF
)
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
        log_error "Failed to post reply via GraphQL: $error_msg"
        exit 1
    fi
}

# Convert comment node ID to database ID
get_database_id_from_node() {
    local node_id="$1"

    # Safely encode node_id as JSON to prevent injection
    local node_id_json
    node_id_json=$(echo "$node_id" | jq -Rs '.')

    local response
    response=$(cat << EOF | gh api graphql --input -
{
  "query": "query(\$nodeId: ID!) { node(id: \$nodeId) { ... on PullRequestReviewComment { databaseId } } }",
  "variables": { "nodeId": $node_id_json }
}
EOF
)
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
        log_error "Failed to get database ID from node: $error_msg"
        exit 1
    fi

    # Extract database ID
    local db_id
    db_id=$(echo "$response" | jq -r '.data.node.databaseId // empty')

    if [[ -z "$db_id" ]]; then
        log_error "Could not get database ID for node: $node_id"
        exit 1
    fi

    echo "$db_id"
}

# Resolve a review thread (posts reply then resolves)
action_resolve() {
    local pr_number="$1"
    local id="$2"
    local response_text="$3"

    local thread_id

    # Determine ID type and handle accordingly
    if [[ "$id" =~ ^[0-9]+$ ]]; then
        # Numeric comment database ID - use REST API to post reply, then resolve
        thread_id=$(get_thread_id_from_comment "$pr_number" "$id")
        post_reply_rest "$pr_number" "$id" "$response_text"
    elif [[ "$id" =~ ^PRRT_[a-zA-Z0-9_-]+$ ]]; then
        # Thread ID - use GraphQL for both reply and resolve
        thread_id="$id"
        post_reply_graphql "$thread_id" "$response_text"
    elif [[ "$id" =~ ^PRRC_[a-zA-Z0-9_-]+$ ]]; then
        # Comment node ID - convert to databaseId, then use REST flow
        local db_id
        db_id=$(get_database_id_from_node "$id")
        thread_id=$(get_thread_id_from_comment "$pr_number" "$db_id")
        post_reply_rest "$pr_number" "$db_id" "$response_text"
    else
        log_error "Invalid ID format: $id. Expected numeric ID, PRRT_xxx thread ID, or PRRC_xxx comment ID"
        exit 1
    fi

    # Resolve the thread using GraphQL
    # shellcheck disable=SC2016
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

# Display usage information
usage() {
    cat << EOF
Usage: $0 <pr_number> <id> <response_text>

Arguments:
  pr_number      Pull request number
  id             Comment ID, Thread ID, or Comment Node ID:
                 - Numeric comment database ID (e.g., 2566690774)
                 - Thread node ID (e.g., PRRT_kwDOQNO0Es5jvUvj)
                 - Comment node ID (e.g., PRRC_kwDOQNO0Es6Y_JfW)
  response_text  Response text (required)

Behavior:
  Posts a reply to the comment/thread, then marks the review thread as resolved

Examples:
  # Resolve with numeric comment ID
  $0 123 456789 "Fixed in commit abc123"

  # Resolve with thread ID
  $0 123 PRRT_kwDOQNO0Es5jvUvj "Addressed in latest commit"

  # Resolve with comment node ID
  $0 123 PRRC_kwDOQNO0Es6Y_JfW "Done, thanks!"

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
    if [[ $# -lt 3 ]]; then
        usage
    fi

    local pr_number="$1"
    local id="$2"
    local response_text="$3"

    # Validate PR number
    if [[ ! "$pr_number" =~ ^[0-9]+$ ]]; then
        log_error "PR number must be numeric: $pr_number"
        exit 1
    fi

    # Validate response text is provided
    if [[ -z "$response_text" ]]; then
        log_error "Response text is required"
        exit 1
    fi

    # Check prerequisites
    check_gh_auth
    get_repo_info

    # Execute action (always resolve)
    action_resolve "$pr_number" "$id" "$response_text"
}

# Run main function
main "$@"
