# ============================================================
# INSTALL DEPENDENCIES BEFORE RUNNING:
#   pip install requests google-genai
# ============================================================

import requests
import os
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types

# ============================================================
# CONFIGURATION — fill these in before running
# ============================================================
GITHUB_TOKEN = "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"
REPO_OWNER   = "UbiquitousIntelligentSystemBINUS"
REPO_NAME    = "2440030872-JovitoColin-InterpretablePneumoniaDetection"
GITHUB_AUTHOR = "jovitocolin"          # author filter for commits
AI_API_KEY   = "AQ.Ab8RN6JmAf0LwgNWy1NJMd1njHiM_8lH_tw5boUittDAmW6Azg"
OUTPUT_FILE  = "commit_analysis_report.md"
# ============================================================

GITHUB_API_BASE = "https://api.github.com"

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SYSTEM_PROMPT = """
You are an elite Technical Project Manager with 20+ years of hands-on software engineering
experience across large-scale distributed systems, startups, and enterprise codebases.
You have a razor-sharp eye for code quality, architecture decisions, and realistic effort
estimation. You do not flatter — you deliver precise, evidence-based assessments grounded
directly in the code you are given.

When analysing a code diff, you will produce a structured report in the following exact
Markdown format (preserve all headings):

## 🔍 Code Quality Assessment

### Maintainability
<Score X/10>
<2–4 sentences of direct, code-based reasoning referencing specific lines, patterns, or
naming choices from the diff.>

### Modularity
<Score X/10>
<2–4 sentences referencing specific functions, classes, or coupling visible in the diff.>

### Edge Case Coverage
<Score X/10>
<2–4 sentences calling out which edge cases are handled, which are missing, with specific
examples from the diff.>

### Overall Code Quality Score
<Weighted average score X/10>
<1–2 sentence executive summary.>

---

## ⏱️ Estimated Engineering Hours

**Estimated Hours: X–Y hrs**

<3–5 sentences explaining the estimate. Reference: logic complexity, number of distinct
concerns addressed, non-trivial algorithms or data transformations, integration surface
area, and debugging/testing effort implied by the change. Do NOT base the estimate on raw
line count alone.>

---

## 🚩 Key Observations & Recommendations

<Bullet list of 3–5 concrete, actionable observations — things done well and things to
improve — each tied to specific evidence in the diff.>
""".strip()


def get_commits_last_7_days(owner: str, repo: str, author: str) -> list[dict]:
    """Fetch all commits by `author` in the past 7 days from the given repo."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params = {"author": author, "since": since, "per_page": 100}
    commits = []
    page = 1

    while True:
        params["page"] = page
        response = requests.get(url, headers=GITHUB_HEADERS, params=params)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        commits.extend(batch)
        page += 1

    return commits


def get_commit_diff(owner: str, repo: str, sha: str) -> dict:
    """Fetch full commit detail including the patch/diff for each file."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"
    headers = {**GITHUB_HEADERS, "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text   # raw unified diff text


def get_commit_metadata(owner: str, repo: str, sha: str) -> dict:
    """Fetch commit metadata (message, stats, files list)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"
    response = requests.get(url, headers=GITHUB_HEADERS)
    response.raise_for_status()
    return response.json()


def analyse_diff_with_gemini(diff_text: str, commit_message: str, sha: str) -> str:
    """Send the diff to Gemini and return its structured analysis."""
    client = genai.Client(api_key=AI_API_KEY)

    user_prompt = (
        f"Commit SHA: `{sha}`\n"
        f"Commit Message: {commit_message}\n\n"
        "Below is the full unified diff for this commit. Analyse it according to your "
        "instructions.\n\n"
        "```diff\n"
        f"{diff_text}\n"
        "```"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
        ),
    )
    return response.text


def build_markdown_report(analyses: list[dict], repo_owner: str, repo_name: str) -> str:
    """Aggregate all per-commit analyses into a single Markdown report."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 📊 Commit Analysis Report",
        f"",
        f"**Repository:** `{repo_owner}/{repo_name}`  ",
        f"**Period:** Last 7 days  ",
        f"**Generated:** {now_str}  ",
        f"**Total Commits Analysed:** {len(analyses)}",
        f"",
        "---",
        "",
    ]

    for i, entry in enumerate(analyses, start=1):
        sha_short = entry["sha"][:7]
        committed_date = entry["committed_date"]
        message_first_line = entry["message"].splitlines()[0] if entry["message"] else "(no message)"
        files_changed = entry["files_changed"]
        additions = entry["additions"]
        deletions = entry["deletions"]

        lines += [
            f"## Commit {i} — `{sha_short}`",
            f"",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Full SHA** | `{entry['sha']}` |",
            f"| **Date** | {committed_date} |",
            f"| **Message** | {message_first_line} |",
            f"| **Files Changed** | {files_changed} |",
            f"| **Additions** | +{additions} |",
            f"| **Deletions** | -{deletions} |",
            f"",
            "### Analysis",
            "",
            entry["analysis"],
            "",
            "---",
            "",
        ]

    lines += [
        "## 📋 Summary",
        "",
        f"This report was automatically generated by `analyser.py` using the GitHub REST API",
        f"and Google Gemini (`gemini-2.5-flash`). Each diff was evaluated by an AI acting as",
        f"an elite Technical Project Manager with deep engineering expertise.",
        "",
    ]

    return "\n".join(lines)


def main():
    print(f"🔍 Fetching commits from {REPO_OWNER}/{REPO_NAME} by '{GITHUB_AUTHOR}' "
          f"in the last 7 days...")

    commits = get_commits_last_7_days(REPO_OWNER, REPO_NAME, GITHUB_AUTHOR)

    if not commits:
        print("⚠️  No commits found for the specified author in the last 7 days.")
        return

    print(f"✅ Found {len(commits)} commit(s). Fetching diffs and running analysis...\n")

    analyses = []

    for idx, commit in enumerate(commits, start=1):
        sha = commit["sha"]
        sha_short = sha[:7]
        message = commit["commit"]["message"]
        committed_date = commit["commit"]["committer"]["date"]

        print(f"[{idx}/{len(commits)}] Analysing commit {sha_short} — "
              f"{message.splitlines()[0][:60]}...")

        # Fetch raw diff
        diff_text = get_commit_diff(REPO_OWNER, REPO_NAME, sha)

        # Fetch metadata for stats
        meta = get_commit_metadata(REPO_OWNER, REPO_NAME, sha)
        stats = meta.get("stats", {})
        files = meta.get("files", [])

        if not diff_text.strip():
            print(f"  ⚠️  Empty diff for {sha_short}, skipping.\n")
            continue

        # Truncate extremely large diffs to stay within model context limits (~150 KB)
        MAX_DIFF_CHARS = 150_000
        if len(diff_text) > MAX_DIFF_CHARS:
            diff_text = diff_text[:MAX_DIFF_CHARS] + "\n\n[diff truncated — exceeds 150 KB]"
            print(f"  ⚠️  Diff truncated to 150 KB for {sha_short}.")

        # Gemini analysis
        analysis_text = analyse_diff_with_gemini(diff_text, message, sha)

        analyses.append({
            "sha": sha,
            "message": message,
            "committed_date": committed_date,
            "files_changed": len(files),
            "additions": stats.get("additions", 0),
            "deletions": stats.get("deletions", 0),
            "analysis": analysis_text,
        })

        print(f"  ✅ Done.\n")

    # Build and write the report
    report_md = build_markdown_report(analyses, REPO_OWNER, REPO_NAME)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"🎉 Report written to '{OUTPUT_FILE}' ({len(analyses)} commit(s) analysed).")


if __name__ == "__main__":
    main()
