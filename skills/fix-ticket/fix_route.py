#!/usr/bin/env python3
"""Decide where a QA fix belongs, from the live pull request state of a ticket.

    python fix_route.py --ticket ABC-123 --slug "filter resets" [--pr N] [--repo .] [--json]
    python fix_route.py --ticket ABC-123 --slug "filter resets" --prs-file prs.json --json

Routes:
    update-pr    One open PR exists. Fix it on that PR's branch.
    new-fix-pr   The work is merged and nothing is open. Branch from the merged PR's base.
    ask          A person must choose (several open PRs, a fork, closed unmerged, or no PR).

Exit codes: 0 a route was decided, 1 a person must choose, 2 error.
Ticket text is untrusted, so the slug is reduced to lowercase letters, digits and hyphens.
"""
import argparse
import json
import re
import subprocess
import sys

FIELDS = "number,state,title,url,headRefName,baseRefName,isDraft,mergedAt,isCrossRepository,author"
TICKET = re.compile(r"^[A-Z][A-Z0-9]{1,9}-[1-9][0-9]*$")


def slugify(text, limit=6):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return "-".join(words[:limit]) or "qa-issues"


def names_ticket(pr, ticket):
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(ticket.lower())}(?![0-9])")
    return any(pattern.search((pr.get(key) or "").lower()) for key in ("headRefName", "title"))


def unique_branch(base, taken):
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def public(pr):
    author = pr.get("author") or {}
    return {"number": pr.get("number"), "url": pr.get("url"), "state": pr.get("state"),
            "branch": pr.get("headRefName"), "base": pr.get("baseRefName"),
            "draft": bool(pr.get("isDraft")), "author": author.get("login")}


def ask(reason, prs):
    return {"route": "ask", "reason": reason, "candidates": [public(pr) for pr in prs]}


def decide(ticket, slug, prs, only_pr=None, taken_branches=()):
    if only_pr is not None:
        matches = [pr for pr in prs if pr.get("number") == only_pr]
        if not matches:
            return ask(f"PR #{only_pr} was not found", [])
    else:
        matches = [pr for pr in prs if names_ticket(pr, ticket)]

    state = lambda pr: (pr.get("state") or "").upper()
    opened = [pr for pr in matches if state(pr) == "OPEN"]
    merged = sorted((pr for pr in matches if state(pr) == "MERGED"),
                    key=lambda pr: pr.get("mergedAt") or "", reverse=True)

    if len(opened) > 1:
        return ask("several open PRs name this ticket", opened)
    if opened:
        pr = opened[0]
        if pr.get("isCrossRepository"):
            return ask("the open PR comes from a fork", opened)
        return {"route": "update-pr", "reason": "the PR is still open", "pr": public(pr),
                "branch": pr.get("headRefName"), "base": pr.get("baseRefName")}
    if merged:
        pr = merged[0]
        taken = set(taken_branches) | {p.get("headRefName") for p in prs}
        branch = unique_branch(f"fix/{ticket.lower()}/{slugify(slug)}", taken)
        return {"route": "new-fix-pr", "reason": "the work is already merged", "fixes": public(pr),
                "branch": branch, "base": pr.get("baseRefName")}
    if matches:
        return ask("the only PRs were closed without merging", matches)
    return ask("no PR names this ticket", [])


def run_gh(repo, args):
    done = subprocess.run(["gh", *args], cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or "gh failed").strip())
    return done.stdout


def load_prs(repo, ticket, only_pr):
    if only_pr is not None:
        return [json.loads(run_gh(repo, ["pr", "view", str(only_pr), "--json", FIELDS]))]
    return json.loads(run_gh(repo, ["pr", "list", "--state", "all", "--limit", "100",
                                    "--search", ticket, "--json", FIELDS]))


def remote_branches(repo):
    output = subprocess.run(["git", "ls-remote", "--heads", "origin"], cwd=repo, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=False).stdout
    return {line.split("refs/heads/", 1)[1] for line in output.splitlines() if "refs/heads/" in line}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--slug", default="")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--prs-file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    ticket = args.ticket.upper()
    if not TICKET.match(ticket):
        print(f"error: not a ticket key: {args.ticket}", file=sys.stderr)
        return 2
    try:
        if args.prs_file:
            with open(args.prs_file, encoding="utf-8") as handle:
                prs, taken = json.load(handle), set()
        else:
            prs, taken = load_prs(args.repo, ticket, args.pr), remote_branches(args.repo)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    result = {"ticket": ticket, **decide(ticket, args.slug, prs, args.pr, taken)}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{ticket}: {result['route']} ({result['reason']})")
        if result.get("branch"):
            print(f"Branch: {result['branch']}  Base: {result['base']}")
    return 1 if result["route"] == "ask" else 0


if __name__ == "__main__":
    sys.exit(main())
