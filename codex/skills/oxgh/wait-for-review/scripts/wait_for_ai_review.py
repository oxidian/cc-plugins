#!/usr/bin/env python3
"""Wait for AI code review comment on a GitHub PR.

Usage: wait_for_ai_review.py <PR_NUMBER>

Exit codes:
    0 - Review found and complete (outputs review body to stdout)
    1 - Timeout after waiting
    2 - PR not found or gh CLI error
    3 - Review errored
"""

import json
import subprocess
import sys
import time

INITIAL_WAIT_S = 30
POLL_INTERVAL_S = 20
MAX_WAIT_S = 40 * 60


def log(message: str) -> None:
    """Print to stderr so stdout stays clean for the review body."""
    print(message, file=sys.stderr)


def run_gh_command(args: list[str]) -> tuple[int, str]:
    """Run a gh CLI command and return (exit_code, output)."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip()


def get_pr_comments(pr_number: str) -> list[dict]:
    """Fetch all comments from a PR."""
    code, output = run_gh_command(["pr", "view", pr_number, "--json", "comments"])
    if code != 0:
        return []
    try:
        data = json.loads(output)
        return data.get("comments", [])
    except json.JSONDecodeError:
        return []


def find_ai_review_comment(comments: list[dict]) -> str | None:
    """Find the AI Code Review comment body, if present."""
    for comment in comments:
        body = comment.get("body", "")
        if body.startswith("## AI Code Review"):
            return body
    return None


def check_review_status(review_body: str) -> tuple[str, str]:
    """Check the status of an AI review comment.

    Returns: (status, review_body)
        status is one of: "in_progress", "complete", "error", "unknown"
    """
    if "Review in progress" in review_body:
        return "in_progress", review_body
    if review_body.startswith("## AI Code Review\n\nError:"):
        return "error", review_body
    if ":x: **Review failed**" in review_body:
        return "error", review_body
    if "Verdict:" in review_body:
        return "complete", review_body
    return "unknown", review_body


def verify_pr_exists(pr_number: str) -> bool:
    """Check if the PR exists."""
    code, _ = run_gh_command(["pr", "view", pr_number, "--json", "number"])
    return code == 0


def wait_for_review(pr_number: str) -> int:
    """Wait for the AI review to complete on a PR.

    Returns exit code.
    """
    if not verify_pr_exists(pr_number):
        log(f"Error: PR #{pr_number} not found")
        return 2

    log(f"Waiting for AI code review on PR #{pr_number}...")
    log(f"Initial wait: {INITIAL_WAIT_S}s (review needs time to start)")
    time.sleep(INITIAL_WAIT_S)

    elapsed = INITIAL_WAIT_S
    last_status = ""

    while elapsed < MAX_WAIT_S:
        comments = get_pr_comments(pr_number)
        review_body = find_ai_review_comment(comments)

        if review_body:
            status, body = check_review_status(review_body)

            if status == "in_progress":
                if last_status != "in_progress":
                    log("Review in progress...")
                    last_status = "in_progress"
            elif status == "error":
                log("Review completed with error")
                print(body)
                return 3
            elif status == "complete":
                log("Review complete!")
                print(body)
                return 0
            else:
                log("Review found (unknown state)")
                print(body)
                return 0
        elif last_status != "waiting":
            log("No review comment yet, polling...")
            last_status = "waiting"

        # Progress update every minute
        if elapsed % 60 == 0 and elapsed > INITIAL_WAIT_S:
            remaining = MAX_WAIT_S - elapsed
            log(f"Still waiting... {remaining}s remaining")

        time.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S

    log(f"Timeout: No complete review after {MAX_WAIT_S}s")
    log(f"Check manually: gh pr view {pr_number} --web")
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        log("Usage: wait_for_ai_review.py <PR_NUMBER>")
        return 2

    pr_number = sys.argv[1]
    return wait_for_review(pr_number)


if __name__ == "__main__":
    sys.exit(main())
