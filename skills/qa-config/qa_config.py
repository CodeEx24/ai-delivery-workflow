#!/usr/bin/env python3
"""Read, check and resolve QA environments for a project.

  python qa_config.py --repo . show [--json]
  python qa_config.py --repo . check [--env E] [--url U] [--pr N] [--json]
  python qa_config.py --repo . set [--me] key=value [key=value ...]
  python qa_config.py --repo . reset [--me] key [key ...] | --all
  python qa_config.py --repo . init --project KEY --staging-url URL [--auth-url URL]
      [--local-url URL] [--local-auth-url URL] [--staging-deployment NAME] [--preview-deployment NAME]
  python qa_config.py --repo . resolve [--env E] [--url U] [--pr N] [--json]
  python qa_config.py --repo . deployed --env staging|preview --sha SHA [--json]

Team settings live in docs/workflow/qa.config.json and are committed. Personal settings (--me)
live in ~/.claude/qa.machine.json, keyed by project. Secrets live in the gitignored .env.qa.local
and are never printed: this script keeps only the names of the variables it finds.

Exit codes: 0 ok, 1 check failed or not deployed, 2 error, 3 refused (access is blocked) or
deployment state unknown. Standard library only.
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

CONFIG_PATH = Path("docs") / "workflow" / "qa.config.json"
SECRETS_FILE = ".env.qa.local"
SCHEMA = "qa-config/1"
MACHINE_SCHEMA = "qa-machine-config/1"

ENV_NAMES = ("local", "preview", "staging", "production")
ACCESS_VALUES = ("full", "qa-data-only", "smoke-read-only", "blocked")
PRODUCTION_ACCESS = ("smoke-read-only", "blocked")
WRITE_ACCESS = ("full", "qa-data-only")
AUTO_URL = "auto-from-pr"
DEPLOYMENT_KEYS = ("provider", "stagingEnvironment", "previewEnvironment")
PROVIDERS = ("github-deployments",)
ACCOUNT_FIELDS = ("emailEnv", "passwordEnv")
MACHINE_KEYS = ("local.url", "local.authUrl", "defaultEnv", "browser", "headed")
BROWSERS = ("chromium", "chrome", "msedge", "firefox", "webkit")

PROJECT_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,19}$")
ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,30}$")
ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
SENSITIVE_PARAM_RE = re.compile(
    r"token|secret|passw|pwd|api[_-]?key|auth|session|signature|otp|jwt|credential", re.I
)

HTTP_TIMEOUT = 5
GH_TIMEOUT = 20
DEPLOYMENT_PAGE = 30


class QaError(Exception):
    """A user-facing error. Messages name keys, never the values that were supplied."""


class GhError(Exception):
    """GitHub could not answer. Deliberately carries no gh output."""


class SafeParser(argparse.ArgumentParser):
    """argparse echoes bad arguments, and an argument could be a pasted secret."""

    def error(self, message):
        self.exit(2, "error: invalid arguments. Run with --help for usage.\n")


# --- repo and files ---------------------------------------------------------------------------


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def repo_root(start):
    try:
        out = git(start, "rev-parse", "--show-toplevel")
    except OSError:
        raise QaError("git is not available")
    if out.returncode != 0:
        raise QaError("--repo is not inside a git repository")
    return Path(out.stdout.strip())


def main_worktree(root):
    """Return the main worktree's folder, or None when it cannot be determined."""
    out = git(root, "rev-parse", "--git-common-dir")
    if out.returncode != 0:
        return None
    common = Path(out.stdout.strip())
    if not common.is_absolute():
        common = root / common
    common = common.resolve()
    return common.parent if common.name == ".git" else None


def secrets_path(root):
    """The worktree's own secrets file, else the main worktree's copy."""
    own = root / SECRETS_FILE
    if own.is_file():
        return own
    main = main_worktree(root)
    if main is not None and main.resolve() != root.resolve():
        shared = main / SECRETS_FILE
        if shared.is_file():
            return shared
    return None


def secret_names(path):
    """Names with a non-empty value. Values are discarded here and never leave this function."""
    if path is None:
        return set()
    try:
        text = path.read_bytes().decode("utf-8-sig", errors="ignore")
    except OSError:
        return set()
    names = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        name, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            names.add(name.strip())
    return names


def is_gitignored(path):
    return git(path.parent, "check-ignore", "-q", "--", path.name).returncode == 0


def ensure_gitignored(root):
    """Add the secrets file to .gitignore if it is not ignored yet. Returns True when added."""
    if git(root, "check-ignore", "-q", "--", SECRETS_FILE).returncode == 0:
        return False
    path = root / ".gitignore"
    existing = path.read_bytes() if path.exists() else b""
    prefix = b"" if not existing or existing.endswith(b"\n") else b"\n"
    with open(path, "ab") as handle:  # Append as bytes so the file's line endings are untouched.
        handle.write(prefix + SECRETS_FILE.encode("ascii") + b"\n")
    return True


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_json(path, body):
    write_text(path, json.dumps(body, indent=2, ensure_ascii=False) + "\n")


# --- URLs and hosts ---------------------------------------------------------------------------


def clean_url(raw, label, allow_query=False):
    """Validate a URL. Errors name the setting only, because a bad value may hold a credential."""
    text = str(raw).strip()
    if not text or "\\" in text or any(c.isspace() or ord(c) < 32 for c in text):
        raise QaError(f"{label} is not a valid URL")
    try:
        parts = urlsplit(text)
        parts.port
    except ValueError:
        raise QaError(f"{label} is not a valid URL")
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise QaError(f"{label} must be an http or https URL")
    if "@" in parts.netloc:
        raise QaError(f"{label} must not contain a username or password")
    if not parts.hostname.isascii():
        raise QaError(f"{label} must use an ASCII (punycode) hostname")
    if not allow_query and (parts.query or parts.fragment):
        raise QaError(f"{label} must be a base URL with no query or fragment")
    for chunk in (parts.query, parts.fragment):
        for name, _ in parse_qsl(chunk, keep_blank_values=True):
            if SENSITIVE_PARAM_RE.search(name):
                raise QaError(f"{label} carries a credential-like parameter. Remove it")
    return text


def host_of(url):
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def port_of(url):
    parts = urlsplit(url)
    return parts.port or {"http": 80, "https": 443}.get(parts.scheme.lower())


def strip_www(host):
    return host[4:] if host.startswith("www.") else host


def host_matches(host, pattern):
    """Exact host, or a proper subdomain for *.suffix. Never a substring."""
    pattern = pattern.lower()
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return host.endswith(suffix) and len(host) > len(suffix)
    return host == pattern


def is_local_host(host):
    return (
        host in ("localhost", "::1", "0.0.0.0", "host.docker.internal")
        or re.fullmatch(r"127(\.\d{1,3}){3}", host) is not None
        or host.endswith((".localhost", ".local", ".test"))
    )


def valid_host_pattern(pattern):
    if not isinstance(pattern, str):
        return False
    text = pattern.lower()
    if text.startswith("*."):
        # At least two labels after the wildcard, so "*.com" can never allow a whole TLD.
        return HOST_RE.fullmatch(text[2:]) is not None
    return HOST_RE.fullmatch(text) is not None or text == "localhost"


def env_urls(env):
    return [u for u in (env.get("url"), env.get("authUrl")) if u and u != AUTO_URL]


def classify(url, envs, allowed):
    """Return (environment or None, matchedBy). Production always wins over everything else."""
    host, port = host_of(url), port_of(url)
    production = [strip_www(host_of(u)) for u in env_urls(envs["production"])]
    if strip_www(host) in production:
        return "production", "production-host"
    for name in ("local", "preview", "staging"):
        for known in env_urls(envs[name]):
            if host == host_of(known) and port == port_of(known):
                return name, "environment-host"
    if any(host.endswith("." + known) for known in production):
        return "production", "production-subdomain"
    if any(host_matches(host, pattern) for pattern in allowed):
        return None, "allowedHosts"
    return None, "unknown"


# --- config -----------------------------------------------------------------------------------


def default_config(project):
    return {
        "schema": SCHEMA,
        "project": project,
        "defaultEnv": "staging",
        "environments": {
            "local": {"url": "http://localhost:3000", "authUrl": None, "access": "full"},
            "preview": {"url": AUTO_URL, "authUrl": None, "access": "full"},
            "staging": {"url": None, "authUrl": None, "access": "qa-data-only"},
            "production": {"url": None, "authUrl": None, "access": "blocked"},
        },
        "allowedHosts": [],
        "deployment": {
            "provider": "github-deployments",
            "stagingEnvironment": None,
            "previewEnvironment": None,
        },
        "accounts": {"owner": default_account("owner")},
    }


def default_account(role):
    stem = re.sub(r"[^A-Z0-9]", "_", role.upper())
    return {"emailEnv": f"QA_{stem}_EMAIL", "passwordEnv": f"QA_{stem}_PASSWORD"}


def require_keys(data, allowed, label):
    unknown = [key for key in data if key not in allowed]
    if unknown:
        raise QaError(f"{label} has unknown keys: {', '.join(sorted(map(str, unknown)))}")


def validate(data):
    """Validate a whole team config in place and return it."""
    if not isinstance(data, dict):
        raise QaError(f"{CONFIG_PATH.as_posix()} must be a JSON object")
    require_keys(data, ("schema", "project", "defaultEnv", "environments", "allowedHosts",
                        "deployment", "accounts"), "config")
    if data.get("schema") != SCHEMA:
        raise QaError(f"schema must be {SCHEMA}")
    if not isinstance(data.get("project"), str) or not PROJECT_RE.fullmatch(data["project"]):
        raise QaError("project must be an uppercase key such as ABC")

    envs = data.get("environments")
    if not isinstance(envs, dict) or set(envs) != set(ENV_NAMES):
        raise QaError(f"environments must define exactly: {', '.join(ENV_NAMES)}")
    for name in ENV_NAMES:
        env = envs[name]
        if not isinstance(env, dict):
            raise QaError(f"{name} must be an object")
        require_keys(env, ("url", "authUrl", "access"), name)
        env.setdefault("url", None)
        env.setdefault("authUrl", None)
        if env.get("access") not in ACCESS_VALUES:
            raise QaError(f"{name}.access must be one of: {', '.join(ACCESS_VALUES)}")
        for field in ("url", "authUrl"):
            value = env[field]
            if value is None or (name == "preview" and field == "url" and value == AUTO_URL):
                continue
            if not isinstance(value, str):
                raise QaError(f"{name}.{field} must be a URL or null")
            clean_url(value, f"{name}.{field}")
            if name == "local" and not is_local_host(host_of(value)):
                raise QaError(f"local.{field} must point at this computer (localhost, *.test)")
    if envs["production"]["access"] not in PRODUCTION_ACCESS:
        raise QaError(f"production.access may only be: {', '.join(PRODUCTION_ACCESS)}")

    production = {strip_www(host_of(u)) for u in env_urls(envs["production"])}
    for name in ("local", "preview", "staging"):
        if any(strip_www(host_of(u)) in production for u in env_urls(envs[name])):
            raise QaError(f"{name} must not use the production host")

    if data.get("defaultEnv") not in ENV_NAMES[:3]:
        raise QaError(f"defaultEnv must be one of: {', '.join(ENV_NAMES[:3])}")

    allowed = data.setdefault("allowedHosts", [])
    if not isinstance(allowed, list) or not all(valid_host_pattern(p) for p in allowed):
        raise QaError("allowedHosts must be hostnames or *.domain.tld patterns")
    data["allowedHosts"] = [p.lower() for p in allowed]

    deployment = data.setdefault("deployment", {})
    if not isinstance(deployment, dict):
        raise QaError("deployment must be an object")
    require_keys(deployment, DEPLOYMENT_KEYS, "deployment")
    if deployment.get("provider", PROVIDERS[0]) not in PROVIDERS:
        raise QaError(f"deployment.provider must be one of: {', '.join(PROVIDERS)}")
    for key in DEPLOYMENT_KEYS[1:]:
        value = deployment.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()
                                  or len(value) > 100 or not value.isprintable()):
            raise QaError(f"deployment.{key} must be a GitHub environment name or null")

    accounts = data.setdefault("accounts", {})
    if not isinstance(accounts, dict):
        raise QaError("accounts must be an object")
    for role, account in accounts.items():
        if not ROLE_RE.fullmatch(str(role)):
            raise QaError("account roles must be lowercase names such as owner")
        if not isinstance(account, dict):
            raise QaError(f"accounts.{role} must be an object")
        require_keys(account, ACCOUNT_FIELDS, f"accounts.{role}")
        for field in ACCOUNT_FIELDS:
            value = account.get(field)
            if not isinstance(value, str) or not ENV_VAR_RE.fullmatch(value):
                raise QaError(
                    f"accounts.{role}.{field} must be an environment variable NAME "
                    "(UPPER_CASE), never the value itself"
                )
    return data


def load_team(root):
    path = root / CONFIG_PATH
    if not path.exists():
        raise QaError(f"no {CONFIG_PATH.as_posix()}. Create it with /qa-config init")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise QaError(f"cannot read {CONFIG_PATH.as_posix()}: it is not valid JSON")
    return validate(data)


def machine_path():
    override = os.environ.get("QA_MACHINE_CONFIG")
    return Path(override) if override else Path.home() / ".claude" / "qa.machine.json"


def read_machine():
    """Return (whole file as a dict, warning). A bad file is ignored, never fatal."""
    path = machine_path()
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, f"ignored your personal QA settings: {path} is not valid JSON"
    if not isinstance(data, dict) or not isinstance(data.get("projects", {}), dict):
        return None, f"ignored your personal QA settings: {path} has the wrong shape"
    return data, None


def parse_machine_value(key, raw):
    if key in ("local.url", "local.authUrl"):
        if raw is None or str(raw).strip().lower() in ("", "null", "none"):
            return None
        url = clean_url(raw, key)
        if not is_local_host(host_of(url)):
            raise QaError(f"{key} must point at this computer (localhost, *.test)")
        return url
    if key == "defaultEnv":
        value = str(raw).strip().lower()
        if value not in ENV_NAMES[:3]:
            raise QaError(f"personal defaultEnv must be one of: {', '.join(ENV_NAMES[:3])}")
        return value
    if key == "browser":
        value = str(raw).strip().lower()
        if value not in BROWSERS:
            raise QaError(f"browser must be one of: {', '.join(BROWSERS)}")
        return value
    if key == "headed":
        value = str(raw).strip().lower()
        if value in ("true", "yes", "on"):
            return True
        if value in ("false", "no", "off"):
            return False
        raise QaError("headed must be on or off")
    raise QaError(f"{key} cannot be set with --me. Personal settings: {', '.join(MACHINE_KEYS)}")


def load_personal(project):
    """Return (allowed personal values for this project, warnings)."""
    data, warning = read_machine()
    if data is None:
        return {}, [warning]
    stored = data.get("projects", {}).get(project, {})
    if not isinstance(stored, dict):
        return {}, [f"ignored your personal QA settings for {project}: wrong shape"]
    values, warnings = {}, []
    for key, raw in stored.items():
        if key not in MACHINE_KEYS:
            warnings.append(f"ignored '{key}' in your personal QA settings: it is a team rule")
            continue
        try:
            values[key] = parse_machine_value(key, raw)
        except QaError as exc:
            warnings.append(f"ignored a personal QA setting: {exc}")
    return values, warnings


def save_personal(project, changes, removals=(), clear=False):
    data, warning = read_machine()
    if data is None:
        raise QaError(f"{warning}. Fix or delete that file first")
    projects = data.setdefault("projects", {})
    current = projects.get(project)
    entry = dict(current) if isinstance(current, dict) and not clear else {}
    entry.update(changes)
    for key in removals:
        entry.pop(key, None)
    if entry:
        projects[project] = entry
    else:
        projects.pop(project, None)
    path = machine_path()
    if not projects:
        if path.exists():
            path.unlink()
        return
    write_json(path, {"schema": MACHINE_SCHEMA, "projects": projects})


def effective_envs(team, personal):
    envs = copy.deepcopy(team["environments"])
    for key, field in (("local.url", "url"), ("local.authUrl", "authUrl")):
        if key in personal:
            envs["local"][field] = personal[key]
    return envs


def apply_team(data, key, raw):
    parts = key.split(".")
    text = str(raw).strip()
    nullable = None if text.lower() in ("", "null", "none") else text
    if key == "defaultEnv":
        data["defaultEnv"] = text.lower()
    elif key == "allowedHosts":
        data["allowedHosts"] = [p.strip() for p in text.split(",") if p.strip()]
    elif len(parts) == 2 and parts[0] in ENV_NAMES and parts[1] in ("url", "authUrl"):
        data["environments"][parts[0]][parts[1]] = nullable
    elif len(parts) == 2 and parts[0] in ENV_NAMES and parts[1] == "access":
        data["environments"][parts[0]]["access"] = text.lower()
    elif len(parts) == 2 and parts[0] == "deployment" and parts[1] in DEPLOYMENT_KEYS:
        data["deployment"][parts[1]] = nullable
    elif len(parts) == 3 and parts[0] == "accounts" and parts[2] in ACCOUNT_FIELDS:
        if not ROLE_RE.fullmatch(parts[1]):
            raise QaError("account roles must be lowercase names such as owner")
        account = data["accounts"].setdefault(parts[1], default_account(parts[1]))
        account[parts[2]] = text
    else:
        raise QaError(f"unknown setting '{key}'")


def reset_team(data, key):
    fresh = default_config(data["project"])
    parts = key.split(".")
    if key in ("defaultEnv", "allowedHosts"):
        data[key] = fresh[key]
    elif len(parts) == 2 and parts[0] in ENV_NAMES and parts[1] in ("url", "authUrl", "access"):
        data["environments"][parts[0]][parts[1]] = fresh["environments"][parts[0]][parts[1]]
    elif len(parts) == 2 and parts[0] == "deployment" and parts[1] in DEPLOYMENT_KEYS:
        data["deployment"][parts[1]] = fresh["deployment"][parts[1]]
    elif len(parts) == 2 and parts[0] == "accounts":
        data["accounts"].pop(parts[1], None)
    elif len(parts) == 3 and parts[0] == "accounts" and parts[2] in ACCOUNT_FIELDS:
        if parts[1] in data["accounts"]:
            data["accounts"][parts[1]][parts[2]] = default_account(parts[1])[parts[2]]
    else:
        raise QaError(f"unknown setting '{key}'")


def split_pairs(pairs):
    out = []
    for index, pair in enumerate(pairs, 1):
        if "=" not in pair:
            raise QaError(f"argument {index} is not key=value")
        key, raw = pair.split("=", 1)
        out.append((key.strip(), raw))
    return out


# --- GitHub -----------------------------------------------------------------------------------


def run_gh(root, args):
    try:
        out = subprocess.run(
            ["gh", *args], cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=GH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GhError("gh is not available or timed out")
    if out.returncode != 0:
        raise GhError(f"gh exited with code {out.returncode}")
    return out.stdout


def gh_api(root, path):
    try:
        return json.loads(run_gh(root, ["api", path]))
    except ValueError:
        raise GhError("gh returned something that is not JSON")


def gh_repo(root):
    name = run_gh(root, ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", name):
        raise GhError("could not identify the GitHub repository")
    return name


def list_deployments(root, repo, environment, sha=None):
    path = (f"repos/{repo}/deployments?environment={quote(environment, safe='')}"
            f"&per_page={DEPLOYMENT_PAGE}")
    if sha:
        path += f"&sha={sha}"
    rows = gh_api(root, path)
    if not isinstance(rows, list):
        raise GhError("unexpected deployments response")
    return rows


def latest_status(root, repo, deployment_id):
    rows = gh_api(root, f"repos/{repo}/deployments/{int(deployment_id)}/statuses?per_page=1")
    if not isinstance(rows, list):
        raise GhError("unexpected deployment status response")
    return rows[0] if rows else None


def first_success(root, repo, rows):
    """Newest deployment whose latest status is success. Returns (deployment, status, last state)."""
    newest_state = None
    for row in rows:
        status = latest_status(root, repo, row["id"])
        state = (status or {}).get("state")
        newest_state = newest_state or state
        if state == "success":
            return row, status, newest_state
    return None, None, newest_state


def preview_for_pr(root, team, pr):
    name = team["deployment"].get("previewEnvironment")
    if not name:
        raise QaError("deployment.previewEnvironment is not set. Set it with /qa-config")
    try:
        repo = gh_repo(root)
        pull = gh_api(root, f"repos/{repo}/pulls/{int(pr)}")
        sha = pull["head"]["sha"]
        rows = list_deployments(root, repo, name, sha)
        row, status, state = first_success(root, repo, rows)
    except GhError as exc:
        raise QaError(f"could not read the preview deployment for PR {pr} from GitHub: {exc}")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise QaError(f"GitHub returned an unexpected answer for PR {pr}")
    if row is None:
        raise QaError(f"no successful preview deployment for PR {pr} at {sha[:8]} "
                      f"(latest state: {state or 'none'})")
    url = status.get("environment_url")
    if not url:
        raise QaError(f"the preview deployment for PR {pr} has no environment URL")
    return {"url": clean_url(url, "preview deployment URL", allow_query=True), "headSha": sha,
            "deploymentId": row["id"], "prState": pull.get("state")}


def deployed_state(root, team, env, sha):
    result = {"environment": env, "sha": sha, "deployed": "unknown", "deployedSha": None,
              "githubEnvironment": None, "deploymentId": None, "reason": None}
    key = "stagingEnvironment" if env == "staging" else "previewEnvironment"
    name = team["deployment"].get(key)
    if not name:
        result["reason"] = f"deployment.{key} is not set"
        return result
    result["githubEnvironment"] = name
    try:
        repo = gh_repo(root)
        if env == "preview":
            return preview_deployed(root, repo, name, sha, result)
        return staging_deployed(root, repo, name, sha, result)
    except GhError as exc:
        result.update(deployed="unknown", reason=f"GitHub could not answer: {exc}")
        return result
    except (KeyError, TypeError, ValueError, AttributeError):
        result.update(deployed="unknown", reason="GitHub returned an unexpected answer")
        return result


def preview_deployed(root, repo, name, sha, result):
    # A preview environment is shared by every PR, so only the exact commit proves anything.
    full = gh_api(root, f"repos/{repo}/commits/{sha}")["sha"]
    result["sha"] = full
    row, _, state = first_success(root, repo, list_deployments(root, repo, name, full))
    if row is not None:
        result.update(deployed=True, deployedSha=row["sha"], deploymentId=row["id"],
                      reason="successful deployment of this exact commit")
    elif not list_deployments(root, repo, name):
        result["reason"] = "GitHub lists no deployments for this environment. Check its name"
    else:
        result.update(deployed=False,
                      reason=f"no successful deployment of this commit (latest: {state or 'none'})")
    return result


def staging_deployed(root, repo, name, sha, result):
    full = gh_api(root, f"repos/{repo}/commits/{sha}")["sha"]
    result["sha"] = full
    rows = list_deployments(root, repo, name)
    if not rows:
        result["reason"] = "GitHub lists no deployments for this environment. Check its name"
        return result
    row, _, state = first_success(root, repo, rows)
    if row is None:
        if len(rows) >= DEPLOYMENT_PAGE:
            result["reason"] = f"no success in the newest {DEPLOYMENT_PAGE} deployments"
        else:
            result.update(deployed=False, reason=f"no successful deployment (latest: {state})")
        return result
    live = row["sha"]
    result.update(deployedSha=live, deploymentId=row["id"])
    if live == full:
        result.update(deployed=True, reason="this exact commit is deployed")
        return result
    relation = gh_api(root, f"repos/{repo}/compare/{full}...{live}?per_page=1").get("status")
    if relation in ("ahead", "identical"):
        result.update(deployed=True, reason="the deployed commit contains this commit")
    elif relation in ("behind", "diverged"):
        result.update(deployed=False, reason=f"the deployed commit does not contain it ({relation})")
    else:
        result["reason"] = "GitHub could not compare the commits"
    return result


# --- resolve and check ------------------------------------------------------------------------


def resolve_target(root, team, personal, url=None, env=None, pr=None):
    envs = effective_envs(team, personal)
    warnings = []
    extra = {}
    if url:
        target = clean_url(url, "--url", allow_query=True)
        if env or pr:
            warnings.append("--url wins: --env and --pr were ignored")
        name, matched = classify(target, envs, team["allowedHosts"])
        source = "--url"
        if name:
            access, auth = envs[name]["access"], envs[name]["authUrl"]
        elif matched == "allowedHosts":
            access, auth = "qa-data-only", None
        else:
            access, auth = "smoke-read-only", None
        confirm = matched == "unknown" or name == "production"
    else:
        if env:
            name, source = env, "--env"
        elif pr:
            name, source = "preview", "--pr"
        elif "defaultEnv" in personal:
            name, source = personal["defaultEnv"], "personal defaultEnv"
        else:
            name, source = team["defaultEnv"], "team defaultEnv"
        if pr and name != "preview":
            raise QaError("--pr only applies to the preview environment")
        access, auth, target = envs[name]["access"], envs[name]["authUrl"], envs[name]["url"]
        matched, confirm = "environment", name == "production"
        if name == "preview" and pr:
            extra = preview_for_pr(root, team, pr)
            target = extra.pop("url")
            found, matched = classify(target, envs, team["allowedHosts"])
            if found == "production":
                name, access, auth, confirm = "production", envs["production"]["access"], None, True
            elif found in ("local", "staging"):
                # Never let a preview's access apply to another environment's host.
                name, access, auth = found, envs[found]["access"], envs[found]["authUrl"]
                warnings.append(f"the preview URL is the {found} host, so {found} access applies")
            elif found != "preview" and matched == "unknown":
                access, auth, confirm = "smoke-read-only", None, True
                warnings.append("the preview URL is not in allowedHosts, so it needs confirmation")
            if extra.get("prState") and extra["prState"] != "open":
                warnings.append(f"PR {pr} is {extra['prState']}")
        elif target == AUTO_URL:
            raise QaError("preview needs --pr N to find its URL")
        if not target:
            raise QaError(f"no URL configured for {name}. Set it with /qa-config {name}.url=<url>")
    result = {
        "project": team["project"], "environment": name, "url": target, "authUrl": auth,
        "access": access, "requiresConfirmation": confirm, "writesAllowed": access in WRITE_ACCESS,
        "refused": access == "blocked", "matchedBy": matched, "source": source,
        "browser": personal.get("browser"), "headed": personal.get("headed"),
    }
    result.update(extra)
    return result, warnings


def probe(url):
    """Is anything answering? Redirects are not followed, so no other host is contacted."""

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": "qa-config"})
        try:
            with opener.open(request, timeout=HTTP_TIMEOUT) as response:
                return response.status, None
        except urllib.error.HTTPError as exc:
            if exc.code in (405, 501) and method == "HEAD":
                continue
            return exc.code, None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            reason = getattr(exc, "reason", exc)
            return None, type(reason).__name__
    return None, "no response"


def account_report(root, team):
    path = secrets_path(root)
    found = secret_names(path)
    rows = []
    for role, account in sorted(team["accounts"].items()):
        rows.append({
            "role": role,
            "emailEnv": account["emailEnv"],
            "emailPresent": bool(os.environ.get(account["emailEnv"])) or account["emailEnv"] in found,
            "passwordEnv": account["passwordEnv"],
            "passwordPresent": (bool(os.environ.get(account["passwordEnv"]))
                                or account["passwordEnv"] in found),
        })
    return path, rows


def run_check(root, url, env, pr):
    team = load_team(root)
    personal, warnings = load_personal(team["project"])
    problems = []
    report = {"ok": False, "project": team["project"], "target": None, "reachable": None,
              "httpStatus": None, "accounts": [], "secretsFile": None}
    try:
        target, more = resolve_target(root, team, personal, url, env, pr)
        warnings += more
        report["target"] = target
    except QaError as exc:
        target = None
        if env == "preview" and not pr and not url and "--pr" in str(exc):
            warnings.append("preview URL comes from a PR: reachability not checked without --pr")
        else:
            problems.append(str(exc))

    if target:
        if target["refused"]:
            problems.append(f"{target['environment']} access is blocked")
        else:
            status, failure = probe(target["url"])
            report["httpStatus"] = status
            report["reachable"] = status is not None and status < 500
            if status is None:
                problems.append(f"URL is not reachable ({failure})")
            elif status >= 500:
                problems.append(f"URL answered with HTTP {status}")
        if target["requiresConfirmation"]:
            warnings.append("this target needs explicit confirmation before testing")

    path, rows = account_report(root, team)
    report["accounts"] = rows
    report["secretsFile"] = str(path) if path else None
    read_only = bool(target) and target["access"] == "smoke-read-only"
    missing = [row[f"{kind}Env"] for row in rows for kind in ("email", "password")
               if not row[f"{kind}Present"]]
    if missing:
        message = f"missing account variables: {', '.join(missing)}"
        (warnings if read_only else problems).append(message)
    if not rows:
        warnings.append("no QA accounts are configured")
    if path is not None and not is_gitignored(path):
        problems.append(f"{SECRETS_FILE} is not gitignored. Ignore it before using it")

    name = (target or {}).get("environment") or env
    key = {"staging": "stagingEnvironment", "preview": "previewEnvironment"}.get(name)
    if key and not team["deployment"].get(key):
        warnings.append(f"deployment.{key} is not set, so deployed checks will report unknown")
    report.update(ok=not problems, problems=problems, warnings=warnings)
    return report


# --- output -----------------------------------------------------------------------------------


def print_json(body):
    print(json.dumps(body, indent=2))


def print_warnings(warnings):
    for warning in warnings:
        print(f"WARNING: {warning}")


def show(root, as_json):
    team = load_team(root)
    personal, warnings = load_personal(team["project"])
    envs = effective_envs(team, personal)
    path, accounts = account_report(root, team)
    default = personal.get("defaultEnv", team["defaultEnv"])
    if as_json:
        print_json({"schema": SCHEMA, "file": CONFIG_PATH.as_posix(), "machineFile": str(machine_path()),
                    "team": team, "personal": personal, "effective": {"defaultEnv": default,
                    "environments": envs}, "accounts": accounts,
                    "secretsFile": str(path) if path else None, "warnings": warnings})
        return
    print(f"Team settings:  {root / CONFIG_PATH}")
    print(f"Your settings:  {machine_path()}")
    print(f"Secrets file:   {path or 'none found (.env.qa.local)'}")
    print(f"Project:        {team['project']}    Default environment: {default}")
    print(f"\n{'environment':<13}{'access':<18}{'url':<42}auth url")
    for name in ENV_NAMES:
        env = envs[name]
        print(f"{name:<13}{env['access']:<18}{str(env['url'] or '-'):<42}{env['authUrl'] or '-'}")
    print(f"\nAllowed hosts:  {', '.join(team['allowedHosts']) or 'none'}")
    deployment = team["deployment"]
    print(f"Deployments:    staging={deployment.get('stagingEnvironment') or '-'} "
          f"preview={deployment.get('previewEnvironment') or '-'}")
    print("\nAccounts (names only, values are never shown)")
    for row in accounts:
        print(f"  {row['role']}: {row['emailEnv']} {'present' if row['emailPresent'] else 'MISSING'}, "
              f"{row['passwordEnv']} {'present' if row['passwordPresent'] else 'MISSING'}")
    if personal:
        print("\nYour personal values")
        for key, value in personal.items():
            print(f"  {key} = {value}")
    print_warnings(warnings)


def print_target(result, warnings):
    for key in ("environment", "url", "authUrl", "access", "requiresConfirmation", "writesAllowed",
                "matchedBy", "source", "browser", "headed", "headSha", "deploymentId", "prState"):
        if key in result and result[key] is not None:
            print(f"{key:<22}{result[key]}")
    if result["refused"]:
        print("REFUSED: this environment's access is blocked")
    print_warnings(warnings)


def cmd_init(root, args):
    path = root / CONFIG_PATH
    if path.exists():
        raise QaError(f"{CONFIG_PATH.as_posix()} already exists. Change it with /qa-config set")
    data = default_config(args.project.strip().upper())
    env = data["environments"]
    env["staging"]["url"] = args.staging_url
    env["staging"]["authUrl"] = args.auth_url
    if args.local_url:
        env["local"]["url"] = args.local_url
    env["local"]["authUrl"] = args.local_auth_url
    data["deployment"]["stagingEnvironment"] = args.staging_deployment
    data["deployment"]["previewEnvironment"] = args.preview_deployment
    validate(data)
    write_json(path, data)
    added = ensure_gitignored(root)
    print(f"Created {CONFIG_PATH.as_posix()}. Commit it.")
    if added:
        print(f"Added {SECRETS_FILE} to .gitignore. Commit that too.")
    print(f"Put QA credentials in {SECRETS_FILE}: QA_OWNER_EMAIL and QA_OWNER_PASSWORD.")


def cmd_set(root, args):
    team = load_team(root)
    pairs = split_pairs(args.pairs)
    if args.me:
        changes = {key: parse_machine_value(key, raw) for key, raw in pairs}
        save_personal(team["project"], changes)
    else:
        for key, raw in pairs:
            apply_team(team, key, raw)
        write_json(root / CONFIG_PATH, validate(team))
    show(root, False)


def cmd_reset(root, args):
    team = load_team(root)
    if not args.all and not args.keys:
        raise QaError("name the settings to reset, or use --all")
    if args.all and args.keys:
        raise QaError("use either setting names or --all, not both")
    if args.me:
        unknown = [key for key in args.keys if key not in MACHINE_KEYS]
        if unknown:
            raise QaError(f"not personal settings: {', '.join(unknown)}")
        save_personal(team["project"], {}, args.keys, clear=args.all)
    else:
        if args.all:
            team = default_config(team["project"])
        for key in args.keys:
            reset_team(team, key)
        write_json(root / CONFIG_PATH, validate(team))
    show(root, False)


def cmd_resolve(root, args):
    team = load_team(root)
    personal, warnings = load_personal(team["project"])
    result, more = resolve_target(root, team, personal, args.url, args.env, args.pr)
    warnings += more
    if args.json:
        print_json({"ok": not result["refused"], **result, "warnings": warnings})
    else:
        print_target(result, warnings)
    return 3 if result["refused"] else 0


def cmd_check(root, args):
    report = run_check(root, args.url, args.env, args.pr)
    if args.json:
        print_json(report)
    else:
        target = report["target"] or {}
        print(f"Target:     {target.get('environment') or '-'} {target.get('url') or ''}")
        print(f"Access:     {target.get('access') or '-'}")
        print(f"Reachable:  {report['reachable']} (HTTP {report['httpStatus']})")
        for row in report["accounts"]:
            print(f"Account {row['role']}: {row['emailEnv']} "
                  f"{'present' if row['emailPresent'] else 'MISSING'}, {row['passwordEnv']} "
                  f"{'present' if row['passwordPresent'] else 'MISSING'}")
        print_warnings(report["warnings"])
        for problem in report["problems"]:
            print(f"BLOCKING: {problem}")
        print("Result:     " + ("OK" if report["ok"] else "BLOCKED"))
    return 0 if report["ok"] else 1


def cmd_deployed(root, args):
    if not SHA_RE.fullmatch(args.sha):
        raise QaError("--sha must be a 7 to 40 character commit SHA")
    result = deployed_state(root, load_team(root), args.env, args.sha.lower())
    if args.json:
        print_json(result)
    else:
        state = result["deployed"]
        print(f"deployed: {str(state).lower()}")
        print(f"environment: {result['environment']} ({result['githubEnvironment'] or 'not set'})")
        print(f"sha: {result['sha']}")
        print(f"deployed sha: {result['deployedSha'] or 'unknown'}")
        print(f"reason: {result['reason']}")
    return {True: 0, False: 1}.get(result["deployed"], 3)


def build_parser():
    parser = SafeParser(description="QA environments for a project")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show").add_argument("--json", action="store_true")

    for name in ("check", "resolve"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--env", choices=ENV_NAMES)
        cmd.add_argument("--url")
        cmd.add_argument("--pr", type=int)
        cmd.add_argument("--json", action="store_true")

    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("--me", action="store_true")
    set_cmd.add_argument("pairs", nargs="+", metavar="key=value")

    reset_cmd = sub.add_parser("reset")
    reset_cmd.add_argument("--me", action="store_true")
    reset_cmd.add_argument("keys", nargs="*")
    reset_cmd.add_argument("--all", action="store_true")

    init_cmd = sub.add_parser("init")
    init_cmd.add_argument("--project", required=True)
    init_cmd.add_argument("--staging-url", required=True)
    init_cmd.add_argument("--auth-url")
    init_cmd.add_argument("--local-url")
    init_cmd.add_argument("--local-auth-url")
    init_cmd.add_argument("--staging-deployment")
    init_cmd.add_argument("--preview-deployment")

    deployed_cmd = sub.add_parser("deployed")
    deployed_cmd.add_argument("--env", required=True, choices=("staging", "preview"))
    deployed_cmd.add_argument("--sha", required=True)
    deployed_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        root = repo_root(args.repo)
        handler = {"show": lambda: show(root, args.json), "init": lambda: cmd_init(root, args),
                   "set": lambda: cmd_set(root, args), "reset": lambda: cmd_reset(root, args),
                   "resolve": lambda: cmd_resolve(root, args), "check": lambda: cmd_check(root, args),
                   "deployed": lambda: cmd_deployed(root, args)}[args.command]
        return handler() or 0
    except QaError as exc:
        if getattr(args, "json", False):
            print_json({"ok": False, "error": str(exc)})
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
