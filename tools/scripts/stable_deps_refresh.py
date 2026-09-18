#!/usr/bin/env python3
"""Refresh a stable branch's locked dependencies: the DAB pointer, then audited upgrades.

Run from the root of a stable-* checkout that has its submodules:

    uv run --no-project --with packaging python stable_deps_refresh.py --summary out.md

1. Move django-ansible-base to the tip of the branch its .gitmodules entry names.
2. Re-lock. `uv lock` keeps every existing pin and moves only what a constraint
   forces, so this step alone never upgrades anything.
3. Audit the exported requirements with pip-audit. For each vulnerable package, try
   `uv lock --upgrade-package <name>==<lowest fixed version>`. An upgrade that cannot
   resolve (a cap elsewhere blocks it) is reported as blocked, never forced.
4. Regenerate requirements.txt and requirements-build.txt with the same commands as the
   uv-export workflow, re-audit, and write a Markdown summary for the pull request.

The uv cache is disabled throughout: `uv export` re-locks, and cached metadata for the
editable django-ansible-base source hides changes to its dynamic dependencies.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib

from packaging.version import Version

DAB = "django-ansible-base"
PIP_AUDIT = "pip-audit==2.10.1"
EXPORT = [
    "uv", "export", "--format", "requirements-txt", "--hashes", "--no-emit-project",
    "--extra", "container",
    "--no-emit-package", "django-ansible-base",
    "--no-emit-package", "certifi",
    "-o", "requirements.txt",
]  # fmt: skip
BUILD = [
    "uv", "pip", "compile", "--generate-hashes",
    "--python-version", "3.12", "--python-platform", "linux",
    "-o", "requirements-build.txt", "requirements-build.in",
]  # fmt: skip


def run(cmd, check=True):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, capture_output=not check, text=True)


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def locked_versions():
    with open("uv.lock", "rb") as f:
        return {p["name"]: p.get("version") for p in tomllib.load(f).get("package", [])}


def audit():
    """Return {package: {"version": str, "vulns": [{"id", "aliases", "fix_versions"}]}}."""
    with tempfile.NamedTemporaryFile(suffix=".json") as out:
        # pip-audit exits 1 when it finds something; only a missing report is an error.
        run(["uvx", PIP_AUDIT, "-r", "requirements.txt", "--no-deps", "--disable-pip",
             "--format", "json", "-o", out.name], check=False)  # fmt: skip
        if os.path.getsize(out.name) == 0:
            raise SystemExit("pip-audit produced no report; refusing to treat that as clean")
        report = json.load(open(out.name))
    deps = report["dependencies"] if isinstance(report, dict) else report
    return {d["name"]: d for d in deps if d.get("vulns")}


def lowest_fix(current, vulns):
    """Lowest version above `current` that clears every vuln, or None if one has no fix."""
    targets = []
    for v in vulns:
        fixes = [Version(f) for f in v.get("fix_versions") or [] if Version(f) > current]
        if not fixes:
            return None
        targets.append(min(fixes))
    return max(targets)


def refresh():
    old_dab = git("rev-parse", f"HEAD:{DAB}")
    run(["git", "submodule", "update", "--remote", DAB])
    new_dab = git("-C", DAB, "rev-parse", "HEAD")

    before = locked_versions()
    run(["uv", "lock"])
    run(EXPORT)

    blocked, no_fix = [], []
    for name, dep in sorted(audit().items()):
        current = Version(dep["version"])
        target = lowest_fix(current, dep["vulns"])
        ids = [v["id"] for v in dep["vulns"]]
        if target is None:
            no_fix.append((name, dep["version"], ids))
            continue
        result = run(["uv", "lock", "--upgrade-package", f"{name}=={target}"], check=False)
        if result.returncode:
            cause = next(
                (
                    ln.strip().removeprefix("cause: ")
                    for ln in result.stderr.splitlines()
                    if "Because" in ln
                ),
                result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "",
            )
            blocked.append((name, dep["version"], str(target), ids, cause))

    run(EXPORT)
    run(BUILD)
    after = locked_versions()
    moved = {n: (before.get(n), v) for n, v in after.items() if before.get(n) != v}
    removed = sorted(set(before) - set(after))
    return {
        "dab": (old_dab, new_dab),
        "moved": moved,
        "removed": removed,
        "blocked": blocked,
        "no_fix": no_fix,
        "residual": {n: [v["id"] for v in d["vulns"]] for n, d in audit().items()},
    }


def describe(sha):
    try:
        tag = git("-C", DAB, "describe", "--tags", "--exact-match", sha)
    except subprocess.CalledProcessError:
        tag = ""
    return f"`{sha[:8]}`" + (f" ({tag})" if tag else "")


def summarize(r):
    old, new = r["dab"]
    lines = ["## django-ansible-base", ""]
    if old == new:
        lines.append(f"Unchanged at {describe(new)}.")
    else:
        lines.append(f"Moved from {describe(old)} to {describe(new)}.")
    lines += ["", "## Locked versions that moved", ""]
    if r["moved"] or r["removed"]:
        lines += [f"- `{n}` {a or '(new)'} -> {b}" for n, (a, b) in sorted(r["moved"].items())]
        lines += [f"- `{n}` removed" for n in r["removed"]]
    else:
        lines.append("None.")
    if r["blocked"]:
        lines += ["", "## Fix available but blocked", ""]
        for name, cur, want, ids, cause in r["blocked"]:
            lines.append(f"- `{name}` {cur}, needs {want} ({', '.join(ids)}): {cause}")
    if r["no_fix"]:
        lines += ["", "## No fixed version published", ""]
        lines += [f"- `{n}` {cur} ({', '.join(ids)})" for n, cur, ids in r["no_fix"]]
    lines += ["", "## Still flagged by pip-audit after this refresh", ""]
    if r["residual"]:
        lines += [f"- `{n}`: {', '.join(ids)}" for n, ids in sorted(r["residual"].items())]
    else:
        lines.append("Nothing.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", help="write the Markdown summary here")
    args = parser.parse_args()
    os.environ["UV_NO_CACHE"] = "1"
    text = summarize(refresh())
    print(text)
    if args.summary:
        with open(args.summary, "w") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
