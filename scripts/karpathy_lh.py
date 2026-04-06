#!/usr/bin/env python3
"""
Karpathy Lighthouse Loop — KpsDev Quality Director
====================================================
Flow:
  1. Read apps.md → find worst-failing app (or use TARGET_APP env var)
  2. Clone app repo from GitHub
  3. Build file tree + read key config files
  4. Call Qwen3-235B-free (OpenRouter) → identify relevant files + generate fix
  5. Apply fix as safe search/replace patches (max 3 files, whitelisted extensions)
  6. Push branch to app repo
  7. Create GitHub PR
  8. Update Taskmaster task with PR link
  9. Log result to Supabase lh_branch_scores

Models (tried in order, all free):
  - qwen/qwen3-235b-a22b:free  (Qwen3 235B MoE, 22B active — best quality)
  - qwen/qwen-2.5-coder-32b-instruct:free  (Qwen2.5-Coder 32B — strong coding)
  - deepseek/deepseek-r1:free  (DeepSeek R1 — reasoning fallback)

Safety:
  - Search/replace patches only — never full file rewrites
  - Whitelisted extensions: .tsx .ts .jsx .js .css .html .json
  - Blocked paths: .env* .github/ supabase/ node_modules/ .next/ dist/ build/
  - Always creates PR — never auto-merges
  - Max 3 files changed per run
"""

import os, json, re, subprocess, sys, shutil, time
from datetime import datetime, timezone
from pathlib import Path
import urllib.request, urllib.error

# ── Config ─────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GH_PAT             = os.environ.get("GH_PAT", "")
SUPABASE_URL       = os.environ.get("SUPABASE_URL", "https://vjlsmljcceseeywepjoo.supabase.co")
SUPABASE_ANON_KEY  = os.environ.get("SUPABASE_ANON_KEY", "")
TARGET_APP         = os.environ.get("TARGET_APP", "").strip()
THRESHOLD          = 95

MODELS = [
    "qwen/qwen3-235b-a22b:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "deepseek/deepseek-r1:free",
]

SAFE_EXTENSIONS  = {".tsx", ".ts", ".jsx", ".js", ".css", ".html", ".json"}
BLOCKED_PREFIXES = {".env", ".github", "supabase", "node_modules", ".next", "dist", "build", "__pycache__"}
MAX_FILE_CHANGES = 3
MAX_FILE_SIZE    = 80_000   # bytes — skip huge files
APPS_MD_PATH     = Path(__file__).parent.parent / "apps.md"


# ── Helpers ────────────────────────────────────────────────────────────────────

def run(cmd: list, cwd=None, check=True) -> subprocess.CompletedProcess:
    """Run a subprocess command."""
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def http_post(url: str, payload: dict, headers: dict) -> dict:
    """Simple HTTPS POST, returns parsed JSON."""
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def openrouter_call(messages: list, system: str = "") -> str:
    """Call OpenRouter with model fallback. Returns content string."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer":  "https://kpsdev.org",
        "X-Title":       "KpsDev Karpathy Loop",
    }

    for model in MODELS:
        try:
            print(f"  → trying model: {model}")
            payload = {
                "model":      model,
                "max_tokens": 2000,
                "messages":   all_messages,
            }
            resp = http_post("https://openrouter.ai/api/v1/chat/completions", payload, headers)
            content = resp["choices"][0]["message"]["content"]
            if content and len(content.strip()) > 20:
                print(f"  ✓ response from {model}")
                return content.strip()
        except Exception as e:
            print(f"  ✗ {model} failed: {e}")
            time.sleep(2)

    raise RuntimeError("All OpenRouter models failed")


def gh_api(method: str, path: str, body: dict | None = None) -> dict:
    """Call GitHub API."""
    url  = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept":        "application/vnd.github+json",
        "Content-Type":  "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise RuntimeError(f"GitHub API {method} {path} → {e.code}: {body_text}")


def supabase_post(path: str, body: dict) -> dict:
    """POST to Supabase edge function."""
    url = f"{SUPABASE_URL}/functions/v1/{path}"
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    try:
        return http_post(url, body, headers)
    except Exception as e:
        print(f"  Supabase {path} error: {e}")
        return {}


# ── Parse apps.md ──────────────────────────────────────────────────────────────

def parse_apps_md() -> list[dict]:
    """Parse apps table from apps.md. Returns list of app dicts."""
    text  = APPS_MD_PATH.read_text(encoding="utf-8")
    apps  = []

    # Find the Apps table rows
    table_match = re.search(
        r"\| App \| URL \| Repo \| Status \|.*?\n\|[-|]+\|(.*?)(?=\n##|\Z)",
        text, re.DOTALL
    )
    if not table_match:
        raise RuntimeError("Could not find Apps table with Repo column in apps.md")

    for line in table_match.group(1).strip().splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 4:
            apps.append({"name": cols[0], "url": cols[1], "repo": cols[2], "status": cols[3]})

    # Parse scores
    scores_match = re.search(
        r"## Last Known Scores.*?\n\|.*?\n\|[-|]+\|(.*?)(?=\n---|\Z)",
        text, re.DOTALL
    )
    scores_by_app: dict[str, dict] = {}
    if scores_match:
        for line in scores_match.group(1).strip().splitlines():
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) >= 5:
                def parse_score(s):
                    m = re.search(r"\d+", s)
                    return int(m.group()) if m else None
                scores_by_app[cols[0]] = {
                    "Performance":     parse_score(cols[1]),
                    "Accessibility":   parse_score(cols[2]),
                    "Best Practices":  parse_score(cols[3]),
                    "SEO":             parse_score(cols[4]),
                }

    for app in apps:
        app["scores"] = scores_by_app.get(app["name"], {})

    return apps


def pick_target_app(apps: list[dict]) -> dict | None:
    """Pick worst-scoring app with a valid repo configured."""
    if TARGET_APP:
        for app in apps:
            if app["name"].lower() == TARGET_APP.lower():
                return app
        raise RuntimeError(f"TARGET_APP '{TARGET_APP}' not found in apps.md")

    # Find app with lowest minimum score across all categories (worst single score)
    best = None
    best_score = 999
    for app in apps:
        repo = app.get("repo", "")
        if not repo or "FIXME" in repo or "—" in repo:
            continue
        scores = [v for v in app["scores"].values() if v is not None]
        if not scores:
            continue
        failing = [s for s in scores if s < THRESHOLD]
        if not failing:
            continue  # already passing
        worst = min(failing)
        if worst < best_score:
            best_score = worst
            best = app

    return best


# ── Repo file utilities ────────────────────────────────────────────────────────

def is_blocked(path: Path) -> bool:
    parts = set(p.lower() for p in path.parts)
    return bool(parts & BLOCKED_PREFIXES) or path.name.startswith(".env")


def get_file_tree(root: Path, max_depth: int = 4) -> str:
    """Build a compact file tree string."""
    lines = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if is_blocked(rel):
            continue
        depth = len(rel.parts) - 1
        if depth > max_depth:
            continue
        indent = "  " * depth
        lines.append(f"{indent}{rel.name}{'/' if p.is_dir() else ''}")
    return "\n".join(lines[:300])  # cap at 300 lines


def read_file_safe(path: Path) -> str | None:
    """Read file if safe and not too large."""
    if path.suffix not in SAFE_EXTENSIONS:
        return None
    if path.stat().st_size > MAX_FILE_SIZE:
        return f"[file too large: {path.stat().st_size} bytes]"
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


ALWAYS_READ = ["vercel.json", "next.config.ts", "next.config.js",
               "vite.config.ts", "vite.config.js", "package.json", "index.html"]

def read_key_files(root: Path) -> dict[str, str]:
    """Read always-included config files."""
    result = {}
    for name in ALWAYS_READ:
        p = root / name
        if p.exists():
            content = read_file_safe(p)
            if content:
                result[str(p.relative_to(root))] = content
    return result


# ── AI Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_IDENTIFY = """You are a Lighthouse performance expert for a React/TypeScript/Next.js/Vite web app.
Given a file tree and key config files, identify the 3-5 source files most likely causing specific Lighthouse failures.
Output ONLY a JSON array of relative file paths. No explanation. Example:
["src/components/Hero.tsx", "src/pages/index.tsx", "public/index.html"]"""

SYSTEM_FIX = """You are a Lighthouse performance expert generating minimal, safe code fixes.
You will receive failing Lighthouse categories with scores, and source file contents.
Generate targeted search/replace patches to fix the failures.

RULES:
- Only fix what is clearly causing the Lighthouse failure
- Each patch: exact string to find + exact replacement (both must be non-empty)
- Max 3 file changes total
- Never touch .env files, secrets, or auth logic
- For Performance: add lazy loading, preconnect, defer scripts, compress images, remove render-blocking
- For Accessibility: add aria-labels, fix contrast, add alt text, fix heading order, add landmark roles
- For SEO: add/fix meta tags, robots.txt, canonical links, structured data
- For Best Practices: add CSP headers in vercel.json, fix deprecated APIs, add HTTPS

Output ONLY valid JSON in this exact format:
{
  "analysis": "one sentence describing root cause",
  "fixes": [
    {
      "file": "relative/path/to/file.tsx",
      "description": "what this fixes",
      "search": "exact string to find (must exist in file)",
      "replace": "exact replacement string"
    }
  ],
  "pr_title": "fix(lighthouse): short description [AppName]",
  "pr_body": "## What\\n...\\n## Why\\n...\\n## Lighthouse impact\\n..."
}"""


def extract_json(text: str) -> dict:
    """Extract first JSON object from AI response."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    # Find JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in AI response: {text[:200]}")
    return json.loads(match.group())


def extract_json_array(text: str) -> list:
    """Extract first JSON array from AI response."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array in AI response: {text[:200]}")
    return json.loads(match.group())


# ── Apply patches ──────────────────────────────────────────────────────────────

def apply_patches(fixes: list[dict], repo_root: Path) -> list[str]:
    """Apply search/replace patches. Returns list of modified file paths (relative)."""
    modified = []
    for fix in fixes[:MAX_FILE_CHANGES]:
        rel_path = fix.get("file", "").strip().lstrip("/")
        search   = fix.get("search", "")
        replace  = fix.get("replace", "")

        if not rel_path or not search or search == replace:
            print(f"  ✗ skip invalid patch for {rel_path}")
            continue

        full_path = repo_root / rel_path
        if is_blocked(Path(rel_path)):
            print(f"  ✗ skip blocked path: {rel_path}")
            continue
        if full_path.suffix not in SAFE_EXTENSIONS:
            print(f"  ✗ skip unsafe extension: {rel_path}")
            continue
        if not full_path.exists():
            print(f"  ✗ file not found: {rel_path}")
            continue

        content = full_path.read_text(encoding="utf-8")
        if search not in content:
            print(f"  ✗ search string not found in {rel_path}")
            continue

        patched = content.replace(search, replace, 1)
        full_path.write_text(patched, encoding="utf-8")
        modified.append(rel_path)
        print(f"  ✓ patched {rel_path}: {fix.get('description', '')}")

    return modified


# ── Git + GitHub ───────────────────────────────────────────────────────────────

def clone_repo(repo: str, dest: Path):
    """Clone repo using GH_PAT."""
    url = f"https://{GH_PAT}@github.com/{repo}.git"
    run(["git", "clone", "--depth=1", url, str(dest)])
    run(["git", "config", "user.name",  "karpathy-bot"],  cwd=dest)
    run(["git", "config", "user.email", "bot@kpsdev.org"], cwd=dest)


def push_branch(repo_root: Path, branch: str, modified_files: list[str]):
    """Stage modified files, commit, and push branch."""
    run(["git", "checkout", "-b", branch], cwd=repo_root)
    for f in modified_files:
        run(["git", "add", f], cwd=repo_root)
    run(["git", "commit", "-m", f"fix(lighthouse): karpathy loop auto-fix [{branch}]"], cwd=repo_root)
    run(["git", "push", "origin", branch], cwd=repo_root)


def create_pr(repo: str, branch: str, pr_title: str, pr_body: str) -> str:
    """Create GitHub PR and return its URL."""
    # Get default branch
    repo_info    = gh_api("GET", f"/repos/{repo}")
    default_branch = repo_info.get("default_branch", "main")

    pr = gh_api("POST", f"/repos/{repo}/pulls", {
        "title": pr_title,
        "body":  pr_body,
        "head":  branch,
        "base":  default_branch,
    })
    return pr.get("html_url", "")


# ── Logging ────────────────────────────────────────────────────────────────────

def log_to_supabase(app_name: str, branch: str, pr_url: str,
                    failing_categories: list[str], scores: dict,
                    model: str, analysis: str):
    """Log each failing category to lh_branch_scores via edge function."""
    for cat in failing_categories:
        supabase_post("create-lh-result", {
            "app_name":        app_name,
            "branch":          branch,
            "pr_url":          pr_url,
            "category":        cat,
            "score_before":    scores.get(cat),
            "model":           model,
            "fix_description": analysis,
            "status":          "pending",
        })


def update_taskmaster_task(app_name: str, category: str, score: int, pr_url: str):
    """Update existing Taskmaster task with PR link."""
    title = f"[Lighthouse] {app_name} — {category} {score}/100"
    # Use create-task (deduplication means it won't create duplicate if task exists)
    # We add PR URL to the description
    desc = (
        f"Lighthouse audit failed threshold ({THRESHOLD}).\n"
        f"App: {app_name}\n"
        f"Category: {category}\n"
        f"Score: {score}/100\n"
        f"Karpathy fix PR: {pr_url}\n"
        f"Merge PR and await next audit to verify improvement."
    )
    supabase_post("create-task", {
        "title":       title,
        "description": desc,
        "priority":    80 if score < 80 else 60,
        "url":         pr_url,
    })


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("═" * 60)
    print("Karpathy Lighthouse Loop")
    print(f"Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 60)

    if not GH_PAT:
        print("ERROR: GH_PAT not set — cannot clone repos")
        sys.exit(1)
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    # 1. Find target app
    apps = parse_apps_md()
    app  = pick_target_app(apps)
    if not app:
        print("✓ All apps passing 95+ threshold — nothing to fix today")
        sys.exit(0)

    print(f"\n📍 Target app: {app['name']} ({app['repo']})")
    failing_cats = {cat: score for cat, score in app["scores"].items()
                    if score is not None and score < THRESHOLD}
    print(f"   Failing: {', '.join(f'{k}={v}' for k, v in failing_cats.items())}")

    # 2. Clone repo
    tmpdir = Path("/tmp/karpathy-lh")
    if tmpdir.exists():
        shutil.rmtree(tmpdir)
    tmpdir.mkdir(parents=True)
    repo_root = tmpdir / "repo"

    print(f"\n📦 Cloning {app['repo']}...")
    clone_repo(app["repo"], repo_root)

    # 3. Build context
    print("\n📂 Building file tree...")
    file_tree   = get_file_tree(repo_root)
    config_files = read_key_files(repo_root)
    config_text  = "\n\n".join(
        f"=== {path} ===\n{content}" for path, content in config_files.items()
    )

    failing_summary = "\n".join(
        f"- {cat}: {score}/100 (need {THRESHOLD}+)" for cat, score in failing_cats.items()
    )

    # 4. AI Pass 1: identify relevant files
    print("\n🤖 AI Pass 1: identifying relevant files...")
    identify_prompt = (
        f"App: {app['name']} ({app['url']})\n"
        f"Failing Lighthouse categories:\n{failing_summary}\n\n"
        f"File tree:\n{file_tree}\n\n"
        f"Key config files:\n{config_text}\n\n"
        "List the 3-5 source files most likely causing these specific failures."
    )

    try:
        identify_response = openrouter_call(
            [{"role": "user", "content": identify_prompt}],
            system=SYSTEM_IDENTIFY
        )
        candidate_files = extract_json_array(identify_response)
    except Exception as e:
        print(f"  ✗ File identification failed: {e}")
        candidate_files = []

    # 5. Read candidate source files
    source_context = ""
    for rel in candidate_files[:6]:
        rel_clean = rel.strip().lstrip("/")
        fpath = repo_root / rel_clean
        if fpath.exists() and not is_blocked(Path(rel_clean)):
            content = read_file_safe(fpath)
            if content:
                source_context += f"\n\n=== {rel_clean} ===\n{content}"

    if not source_context:
        print("  ⚠ No candidate files read — using config files only")
        source_context = config_text

    # 6. AI Pass 2: generate fix
    print("\n🤖 AI Pass 2: generating fix...")
    fix_prompt = (
        f"App: {app['name']} ({app['url']})\n"
        f"Failing Lighthouse categories:\n{failing_summary}\n\n"
        f"Source files:\n{source_context}\n\n"
        "Generate targeted search/replace patches to fix these Lighthouse failures."
    )

    fix_response = openrouter_call(
        [{"role": "user", "content": fix_prompt}],
        system=SYSTEM_FIX
    )

    try:
        fix_data = extract_json(fix_response)
    except Exception as e:
        print(f"  ✗ Fix JSON parse failed: {e}\nRaw response: {fix_response[:500]}")
        sys.exit(1)

    fixes    = fix_data.get("fixes", [])
    analysis = fix_data.get("analysis", "")
    pr_title = fix_data.get("pr_title", f"fix(lighthouse): auto-fix [{app['name']}]")
    pr_body  = fix_data.get("pr_body", f"Karpathy loop auto-fix for {app['name']}")

    if not fixes:
        print("  ✗ No fixes generated — skipping")
        sys.exit(0)

    print(f"  Analysis: {analysis}")
    print(f"  Fixes proposed: {len(fixes)}")

    # 7. Apply patches
    print("\n🔧 Applying patches...")
    modified = apply_patches(fixes, repo_root)

    if not modified:
        print("  ✗ No patches applied — search strings may not match current code")
        sys.exit(1)

    # 8. Push branch + create PR
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    branch    = f"karpathy/lh-{app['name'].lower().replace(' ', '-')}-{timestamp}"

    print(f"\n🚀 Pushing branch: {branch}")
    push_branch(repo_root, branch, modified)

    print("📬 Creating PR...")
    pr_url = create_pr(app["repo"], branch, pr_title, pr_body)
    print(f"  PR: {pr_url}")

    # 9. Log + update Taskmaster
    print("\n📊 Logging results...")
    log_to_supabase(
        app_name=app["name"],
        branch=branch,
        pr_url=pr_url,
        failing_categories=list(failing_cats.keys()),
        scores=failing_cats,
        model=MODELS[0],
        analysis=analysis,
    )

    for cat, score in failing_cats.items():
        update_taskmaster_task(app["name"], cat, score, pr_url)

    # 10. Summary
    print("\n" + "═" * 60)
    print(f"✅ Karpathy loop complete")
    print(f"   App:     {app['name']}")
    print(f"   Fixed:   {', '.join(modified)}")
    print(f"   PR:      {pr_url}")
    print(f"   Review and merge. Next audit will verify improvement.")
    print("═" * 60)


if __name__ == "__main__":
    main()
