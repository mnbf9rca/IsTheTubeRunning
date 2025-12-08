#!/usr/bin/env bash
#
# gh_pr_comments_fetch.sh
# Fetch PR comments with full context for agent consumption
#
# Usage:
#   gh_pr_comments_fetch.sh <pr_number> [options]
#
# Arguments:
#   pr_number           - Pull request number
#
# Options:
#   --type <type>       - Filter by type: threads|issues|pr-reviews|all (default: all)
#                         threads = inline code review threads only
#                         issues = issue comments only
#                         pr-reviews = PR review bodies only
#                         all = everything (threads + issues + pr-reviews)
#   --status <status>   - Filter by status: unresolved|resolved|all (default: all)
#                         Note: Only applies to inline threads, not PR reviews or issues
#   --format <format>   - Output format: json|summary (default: json)
#   --page <n>          - Page number for GraphQL cursor-based pagination (default: 1)
#   --per-page <n>      - Items per page (default: 50, max: 100)
#
# Environment:
#   GITHUB_TOKEN or gh authentication must be configured
#
# Output:
#   JSON or summary format with threads, comments, PR reviews, and pagination info
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

# Fetch review threads using GraphQL with pagination
fetch_review_threads() {
    local pr_number="$1"
    local per_page="$2"
    local page="$3"
    local status_filter="$4"

    # Calculate cursor for pagination (GraphQL uses cursor-based pagination)
    # To reach page N, we must fetch pages 1 through N-1 to get the cursor
    # This is necessary because GraphQL limits 'first' to 100 items
    local after_cursor=""
    if [[ $page -gt 1 ]]; then
        # Loop through pages 1 to N-1, extracting endCursor from each
        local current_page=1
        local cursor_query
        # shellcheck disable=SC2016
        cursor_query='query($owner: String!, $repo: String!, $pr: Int!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}'

        while [[ $current_page -lt $page ]]; do
            local cursor_response
            if [[ -n "$after_cursor" ]]; then
                cursor_response=$(gh api graphql \
                    -f query="$cursor_query" \
                    -f owner="$REPO_OWNER" \
                    -f repo="$REPO_NAME" \
                    -F pr="$pr_number" \
                    -F first="$per_page" \
                    -f after="$after_cursor")
            else
                cursor_response=$(gh api graphql \
                    -f query="$cursor_query" \
                    -f owner="$REPO_OWNER" \
                    -f repo="$REPO_NAME" \
                    -F pr="$pr_number" \
                    -F first="$per_page")
            fi

            # Extract the endCursor for the next iteration
            local cursor
            cursor=$(echo "$cursor_response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // empty')

            # Check if there's a next page
            local has_next
            has_next=$(echo "$cursor_response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage')

            if [[ "$has_next" == "false" ]]; then
                # We've reached the end, no more pages available
                break
            fi

            if [[ -n "$cursor" ]]; then
                after_cursor="$cursor"
            else
                # No cursor means no more pages
                break
            fi

            current_page=$((current_page + 1))
        done
    fi

    # Main query for review threads
    # shellcheck disable=SC2016
    local query='query($owner: String!, $repo: String!, $pr: Int!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      reviewThreads(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        totalCount
        nodes {
          id
          isResolved
          path
          line
          startLine
          diffSide
          comments(first: 100) {
            nodes {
              id
              databaseId
              body
              author {
                login
              }
              createdAt
            }
          }
        }
      }
    }
  }
}'

    local response
    if [[ -n "$after_cursor" ]]; then
        response=$(gh api graphql \
            -f query="$query" \
            -f owner="$REPO_OWNER" \
            -f repo="$REPO_NAME" \
            -F pr="$pr_number" \
            -F first="$per_page" \
            -f after="$after_cursor")
    else
        response=$(gh api graphql \
            -f query="$query" \
            -f owner="$REPO_OWNER" \
            -f repo="$REPO_NAME" \
            -F pr="$pr_number" \
            -F first="$per_page")
    fi
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

    # Filter threads by status if needed
    local filtered_threads
    case "$status_filter" in
        unresolved)
            filtered_threads=$(echo "$response" | jq '.data.repository.pullRequest.reviewThreads.nodes | map(select(.isResolved == false))')
            ;;
        resolved)
            filtered_threads=$(echo "$response" | jq '.data.repository.pullRequest.reviewThreads.nodes | map(select(.isResolved == true))')
            ;;
        all)
            filtered_threads=$(echo "$response" | jq '.data.repository.pullRequest.reviewThreads.nodes')
            ;;
        *)
            log_error "Invalid status filter: $status_filter"
            exit 1
            ;;
    esac

    # Return both filtered threads and pagination info
    jq -n \
        --argjson threads "$filtered_threads" \
        --arg title "$(echo "$response" | jq -r '.data.repository.pullRequest.title')" \
        --argjson pageInfo "$(echo "$response" | jq '.data.repository.pullRequest.reviewThreads.pageInfo')" \
        --argjson totalCount "$(echo "$response" | jq '.data.repository.pullRequest.reviewThreads.totalCount')" \
        '{threads: $threads, title: $title, pageInfo: $pageInfo, totalCount: $totalCount}'
}

# Fetch issue comments using REST API with pagination
fetch_issue_comments() {
    local pr_number="$1"
    local per_page="$2"
    local page="$3"

    local response
    response=$(gh api \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/repos/$REPO_OWNER/$REPO_NAME/issues/$pr_number/comments?per_page=$per_page&page=$page")
    local gh_status=$?

    # Check for errors from gh api command
    if [[ $gh_status -ne 0 ]]; then
        log_error "gh api command failed with exit code $gh_status"
        exit 1
    fi

    echo "$response"
}

# Fetch PR reviews using GraphQL
fetch_pr_reviews() {
    local pr_number="$1"

    # shellcheck disable=SC2016
    local query='query($owner: String!, $repo: String!, $pr: Int!, $first: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviews(first: $first) {
        nodes {
          id
          databaseId
          body
          state
          author {
            login
          }
          createdAt
          submittedAt
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
        -F pr="$pr_number" \
        -F first=100)
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
        log_error "Failed to fetch PR reviews: $error_msg"
        exit 1
    fi

    echo "$response" | jq '.data.repository.pullRequest.reviews.nodes'
}

# Fetch PR title using GraphQL (minimal query for metadata only)
fetch_pr_title() {
    local pr_number="$1"

    # shellcheck disable=SC2016
    local query='query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
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
        log_error "Failed to fetch PR title: $error_msg"
        exit 1
    fi

    echo "$response" | jq -r '.data.repository.pullRequest.title'
}

# Format output as JSON
format_json_output() {
    local pr_number="$1"
    local threads_data="$2"
    local issue_comments="$3"
    local pr_reviews="$4"
    local page="$5"
    local per_page="$6"
    local type_filter="$7"
    local status_filter="$8"

    # Extract components from threads_data
    local threads
    threads=$(echo "$threads_data" | jq '.threads')
    local pr_title
    pr_title=$(echo "$threads_data" | jq -r '.title')
    local page_info
    page_info=$(echo "$threads_data" | jq '.pageInfo')
    local total_threads
    total_threads=$(echo "$threads_data" | jq '.totalCount')

    # Transform threads to include actionable IDs
    local transformed_threads
    transformed_threads=$(echo "$threads" | jq 'map({
        thread_id: .id,
        is_resolved: .isResolved,
        path: .path,
        line: .line,
        start_line: .startLine,
        diff_side: .diffSide,
        comments: [.comments.nodes | to_entries[] | {
            comment_id: .value.id,
            database_id: .value.databaseId,
            author: (.value.author.login // "unknown"),
            body: .value.body,
            created_at: .value.createdAt,
            is_first_in_thread: (.key == 0)
        }],
        actionable_id: .id,
        actionable_id_numeric: (.comments.nodes[0].databaseId // null)
    })')

    # Transform issue comments
    local transformed_issue_comments
    transformed_issue_comments=$(echo "$issue_comments" | jq 'map({
        comment_id: .node_id,
        database_id: .id,
        author: (.user.login // "unknown"),
        body: .body,
        created_at: .created_at
    })')

    # Transform PR reviews
    local transformed_pr_reviews
    transformed_pr_reviews=$(echo "$pr_reviews" | jq 'map({
        review_id: .id,
        database_id: .databaseId,
        author: (.author.login // "unknown"),
        body: .body,
        state: .state,
        created_at: .createdAt,
        submitted_at: .submittedAt
    })')

    # Calculate summary statistics
    local unresolved_count
    unresolved_count=$(echo "$threads" | jq '[.[] | select(.isResolved == false)] | length')
    local resolved_count
    resolved_count=$(echo "$threads" | jq '[.[] | select(.isResolved == true)] | length')
    local issue_comments_count
    issue_comments_count=$(echo "$issue_comments" | jq 'length')

    # Calculate PR reviews statistics by state
    local pr_reviews_count
    pr_reviews_count=$(echo "$pr_reviews" | jq 'length')
    local pr_reviews_by_state
    pr_reviews_by_state=$(echo "$pr_reviews" | jq 'group_by(.state) | map({key: .[0].state, value: length}) | from_entries')

    # Calculate filtered count (threads are already filtered by status in fetch_review_threads)
    local filtered_threads_count
    filtered_threads_count=$(echo "$transformed_threads" | jq 'length')

    # Calculate pagination display info based on filtered results
    # Note: When status filter is applied, the counts reflect filtered results
    local start_item=$(( (page - 1) * per_page + 1 ))
    local end_item=$(( start_item + filtered_threads_count - 1 ))

    # Recalculate has_next_page based on filtered results
    # If we got a full page of filtered results, there might be more
    local has_next_page
    if [[ $filtered_threads_count -eq $per_page ]]; then
        # We filled the page, so use the API's hasNextPage
        has_next_page=$(echo "$page_info" | jq -r '.hasNextPage')
    else
        # We didn't fill the page, so there are no more filtered results
        has_next_page="false"
    fi

    # For pagination summary, use filtered count when a status filter is applied
    local display_total_count
    if [[ "$status_filter" != "all" ]]; then
        # We can't know the true filtered total without fetching all pages
        # So we show what we know: we have at least end_item items
        # If has_next_page is true, indicate there are more
        if [[ "$has_next_page" == "true" ]]; then
            display_total_count="$end_item+"
        else
            display_total_count="$end_item"
        fi
    else
        # No filter, use API's total count
        display_total_count="$total_threads"
    fi

    # Build final JSON output
    jq -n \
        --argjson pr_number "$pr_number" \
        --arg repository "$REPO_OWNER/$REPO_NAME" \
        --arg pr_title "$pr_title" \
        --arg fetched_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
        --argjson page "$page" \
        --argjson per_page "$per_page" \
        --argjson start_item "$start_item" \
        --argjson end_item "$end_item" \
        --arg has_next_page "$has_next_page" \
        --arg display_total_count "$display_total_count" \
        --argjson total_threads "$total_threads" \
        --argjson threads "$transformed_threads" \
        --argjson issue_comments "$transformed_issue_comments" \
        --argjson pr_reviews "$transformed_pr_reviews" \
        --argjson unresolved_threads "$unresolved_count" \
        --argjson resolved_threads "$resolved_count" \
        --argjson total_issue_comments "$issue_comments_count" \
        --argjson total_pr_reviews "$pr_reviews_count" \
        --argjson pr_reviews_by_state "$pr_reviews_by_state" \
        '{
            pr_number: $pr_number,
            repository: $repository,
            pr_title: $pr_title,
            fetched_at: $fetched_at,
            pagination: {
                page: $page,
                per_page: $per_page,
                start_item: $start_item,
                end_item: $end_item,
                has_next_page: ($has_next_page == "true"),
                total_count: $display_total_count,
                summary: "Showing items \($start_item)-\($end_item) of \($display_total_count), use --page \($page + 1) for more"
            },
            threads: $threads,
            issue_comments: $issue_comments,
            pr_reviews: $pr_reviews,
            summary: {
                inline_threads: {
                    total: $total_threads,
                    unresolved: $unresolved_threads,
                    resolved: $resolved_threads
                },
                pr_reviews: {
                    total: $total_pr_reviews,
                    by_state: $pr_reviews_by_state,
                    warning: "Limited to first 100 reviews (no pagination)"
                },
                issue_comments: {
                    total: $total_issue_comments,
                    warning: "Count reflects current page only (page \($page))"
                }
            }
        }'
}

# Format output as human-readable summary
format_summary_output() {
    local json_output="$1"

    local pr_number
    pr_number=$(echo "$json_output" | jq -r '.pr_number')
    local pr_title
    pr_title=$(echo "$json_output" | jq -r '.pr_title')
    local repository
    repository=$(echo "$json_output" | jq -r '.repository')
    local pagination_summary
    pagination_summary=$(echo "$json_output" | jq -r '.pagination.summary')

    echo "PR #$pr_number: $pr_title"
    echo "Repository: $repository"
    echo ""

    # Display review threads
    local threads_count
    threads_count=$(echo "$json_output" | jq '.threads | length')
    if [[ $threads_count -gt 0 ]]; then
        echo "== Review Threads ($threads_count) =="
        echo ""

        local thread_index=1
        while IFS= read -r thread; do
            local thread_id
            thread_id=$(echo "$thread" | jq -r '.thread_id')
            local is_resolved
            is_resolved=$(echo "$thread" | jq -r '.is_resolved')
            local path
            path=$(echo "$thread" | jq -r '.path')
            local line
            line=$(echo "$thread" | jq -r '.line')
            local first_comment
            first_comment=$(echo "$thread" | jq -r '.comments[0]')
            local author
            author=$(echo "$first_comment" | jq -r '.author')
            # Fallback for null or empty author
            if [[ -z "$author" || "$author" == "null" ]]; then
                author="(deleted user)"
            fi
            local body
            body=$(echo "$first_comment" | jq -r '.body')
            local body_preview
            body_preview=$(echo "$body" | head -c 100)
            local replies_count
            replies_count=$(( $(echo "$thread" | jq '.comments | length') - 1 ))
            local actionable_id
            actionable_id=$(echo "$thread" | jq -r '.actionable_id_numeric')

            local status_marker="[ ]"
            if [[ "$is_resolved" == "true" ]]; then
                status_marker="[✓]"
            fi

            echo "[$thread_index] $status_marker $thread_id (Line $line in $path)"
            echo "    Author: $author"
            if [[ ${#body} -gt 100 ]]; then
                echo "    \"$body_preview...\""
            else
                echo "    \"$body_preview\""
            fi
            echo "    Replies: $replies_count | Actionable ID: $actionable_id"
            echo ""

            thread_index=$((thread_index + 1))
        done < <(echo "$json_output" | jq -c '.threads[]')
    fi

    # Display issue comments
    local issue_comments_count
    issue_comments_count=$(echo "$json_output" | jq '.issue_comments | length')
    if [[ $issue_comments_count -gt 0 ]]; then
        echo "== Issue Comments ($issue_comments_count) =="
        echo ""

        local comment_index=1
        while IFS= read -r comment; do
            local comment_id
            comment_id=$(echo "$comment" | jq -r '.comment_id')
            local author
            author=$(echo "$comment" | jq -r '.author')
            # Fallback for null or empty author
            if [[ -z "$author" || "$author" == "null" ]]; then
                author="(deleted user)"
            fi
            local body
            body=$(echo "$comment" | jq -r '.body')
            local body_preview
            body_preview=$(echo "$body" | head -c 100)

            echo "[$comment_index] $comment_id"
            echo "    Author: $author"
            if [[ ${#body} -gt 100 ]]; then
                echo "    \"$body_preview...\""
            else
                echo "    \"$body_preview\""
            fi
            echo ""

            comment_index=$((comment_index + 1))
        done < <(echo "$json_output" | jq -c '.issue_comments[]')
    fi

    # Display PR reviews
    local pr_reviews_count
    pr_reviews_count=$(echo "$json_output" | jq '.pr_reviews | length')
    if [[ $pr_reviews_count -gt 0 ]]; then
        echo "== PR Reviews ($pr_reviews_count) =="
        echo ""

        local review_index=1
        while IFS= read -r review; do
            local review_id
            review_id=$(echo "$review" | jq -r '.review_id')
            local author
            author=$(echo "$review" | jq -r '.author')
            # Fallback for null or empty author
            if [[ -z "$author" || "$author" == "null" ]]; then
                author="(deleted user)"
            fi
            local state
            state=$(echo "$review" | jq -r '.state')
            local body
            body=$(echo "$review" | jq -r '.body')

            echo "[$review_index] $review_id ($state)"
            echo "    Author: $author"
            if [[ -n "$body" && "$body" != "null" && "$body" != "" ]]; then
                local body_preview
                body_preview=$(echo "$body" | head -c 100)
                if [[ ${#body} -gt 100 ]]; then
                    echo "    \"$body_preview...\""
                else
                    echo "    \"$body_preview\""
                fi
            else
                echo "    (no body)"
            fi
            echo ""

            review_index=$((review_index + 1))
        done < <(echo "$json_output" | jq -c '.pr_reviews[]')
    fi

    # Display summary statistics
    echo "== Summary =="
    local total_threads
    total_threads=$(echo "$json_output" | jq -r '.summary.inline_threads.total')
    local unresolved_threads
    unresolved_threads=$(echo "$json_output" | jq -r '.summary.inline_threads.unresolved')
    local resolved_threads
    resolved_threads=$(echo "$json_output" | jq -r '.summary.inline_threads.resolved')
    local total_pr_reviews
    total_pr_reviews=$(echo "$json_output" | jq -r '.summary.pr_reviews.total')
    local total_issue_comments
    total_issue_comments=$(echo "$json_output" | jq -r '.summary.issue_comments.total')

    echo "Inline threads: $total_threads total ($unresolved_threads unresolved, $resolved_threads resolved)"

    # Display PR reviews by state
    if [[ $total_pr_reviews -gt 0 ]]; then
        local states_summary=""
        while IFS= read -r state_entry; do
            local state
            state=$(echo "$state_entry" | jq -r '.key')
            local count
            count=$(echo "$state_entry" | jq -r '.value')
            if [[ -n "$states_summary" ]]; then
                states_summary="$states_summary, "
            fi
            states_summary="$states_summary$count $state"
        done < <(echo "$json_output" | jq -c '.summary.pr_reviews.by_state | to_entries[]')

        echo "PR reviews: $total_pr_reviews ($states_summary) - limited to first 100"
    else
        echo "PR reviews: 0 - limited to first 100"
    fi

    # Get current page from json_output
    local current_page
    current_page=$(echo "$json_output" | jq -r '.pagination.page')

    echo "Issue comments: $total_issue_comments (page $current_page only)"
    echo ""
    echo "== Pagination =="
    echo "$pagination_summary"
}

# Display usage information
usage() {
    cat << EOF
Usage: $0 <pr_number> [options]

Arguments:
  pr_number      Pull request number

Options:
  --type <type>       Filter by type: threads|issues|pr-reviews|all (default: all)
                      threads = inline code review threads only
                      issues = issue comments only
                      pr-reviews = PR review bodies only
                      all = everything (threads + issues + pr-reviews)
  --status <status>   Filter by status: unresolved|resolved|all (default: all)
                      Note: Only applies to inline threads, not PR reviews or issues
  --format <format>   Output format: json|summary (default: json)
  --page <n>          Page number for pagination (default: 1)
  --per-page <n>      Items per page (default: 50, max: 100)

Examples:
  # Fetch all comment types (default)
  $0 123

  # Fetch only inline threads
  $0 123 --type threads

  # Fetch only unresolved inline threads
  $0 123 --type threads --status unresolved

  # Fetch only PR review bodies
  $0 123 --type pr-reviews

  # Fetch all comments as summary
  $0 123 --format summary

  # Fetch resolved threads only with pagination
  $0 123 --type threads --status resolved --page 2 --per-page 100

  # Fetch only issue comments
  $0 123 --type issues

Environment:
  GITHUB_TOKEN or gh authentication must be configured

Output:
  JSON or summary format with full comment context and pagination info

Limitations:
  - PR reviews: Limited to first 100 reviews (no pagination support)
  - Issue comments: Only fetches one page at a time (use --page for more)
  - Inline threads: Full pagination support with --page option

Breaking Changes (v2.0):
  - --type reviews renamed to --type threads
  - Default changed from 'reviews' to 'all' (now includes PR reviews)
  - JSON output structure changed (new pr_reviews section, restructured summary)
EOF
    exit 1
}

# Main function
main() {
    # Default values
    local type_filter="all"
    local status_filter="all"
    local format="json"
    local page=1
    local per_page=50

    # Parse arguments
    if [[ $# -lt 1 ]]; then
        usage
    fi

    local pr_number="$1"
    shift

    # Validate PR number
    if [[ ! "$pr_number" =~ ^[0-9]+$ ]]; then
        log_error "PR number must be numeric: $pr_number"
        exit 1
    fi

    # Parse options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                type_filter="$2"
                if [[ ! "$type_filter" =~ ^(threads|issues|pr-reviews|all)$ ]]; then
                    log_error "Invalid type: $type_filter. Must be threads|issues|pr-reviews|all"
                    exit 1
                fi
                shift 2
                ;;
            --status)
                status_filter="$2"
                if [[ ! "$status_filter" =~ ^(unresolved|resolved|all)$ ]]; then
                    log_error "Invalid status: $status_filter. Must be unresolved|resolved|all"
                    exit 1
                fi
                shift 2
                ;;
            --format)
                format="$2"
                if [[ ! "$format" =~ ^(json|summary)$ ]]; then
                    log_error "Invalid format: $format. Must be json|summary"
                    exit 1
                fi
                shift 2
                ;;
            --page)
                page="$2"
                if [[ ! "$page" =~ ^[0-9]+$ ]] || [[ $page -lt 1 ]]; then
                    log_error "Page must be a positive integer: $page"
                    exit 1
                fi
                shift 2
                ;;
            --per-page)
                per_page="$2"
                if [[ ! "$per_page" =~ ^[0-9]+$ ]] || [[ $per_page -lt 1 ]] || [[ $per_page -gt 100 ]]; then
                    log_error "Per-page must be between 1 and 100: $per_page"
                    exit 1
                fi
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done

    # Check prerequisites
    check_gh_auth
    get_repo_info

    # Fetch data based on type filter
    local threads_data='{"threads": [], "title": "", "pageInfo": {"hasNextPage": false, "endCursor": null}, "totalCount": 0}'
    local issue_comments='[]'
    local pr_reviews='[]'

    if [[ "$type_filter" == "threads" ]] || [[ "$type_filter" == "all" ]]; then
        threads_data=$(fetch_review_threads "$pr_number" "$per_page" "$page" "$status_filter")
    fi

    if [[ "$type_filter" == "issues" ]] || [[ "$type_filter" == "all" ]]; then
        issue_comments=$(fetch_issue_comments "$pr_number" "$per_page" "$page")
    fi

    if [[ "$type_filter" == "pr-reviews" ]] || [[ "$type_filter" == "all" ]]; then
        pr_reviews=$(fetch_pr_reviews "$pr_number")
    fi

    # If we only fetched issue comments or pr-reviews, we need to get the PR title separately
    if [[ "$type_filter" == "issues" ]] || [[ "$type_filter" == "pr-reviews" ]]; then
        local pr_title
        pr_title=$(fetch_pr_title "$pr_number")
        threads_data=$(echo "$threads_data" | jq --arg title "$pr_title" '.title = $title')
    fi

    # Format output
    local json_output
    json_output=$(format_json_output "$pr_number" "$threads_data" "$issue_comments" "$pr_reviews" "$page" "$per_page" "$type_filter" "$status_filter")

    if [[ "$format" == "summary" ]]; then
        format_summary_output "$json_output"
    else
        echo "$json_output"
    fi
}

# Run main function
main "$@"
