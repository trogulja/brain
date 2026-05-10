#!/usr/bin/env python3
"""Bootstrap install for the brain.

Subcommands:
    python install.py [--with-semantic] [--target PATH] [--skill-target PATH] [--force]
        Default install: copy schemas, scripts, .obsidian config, .gitignore,
        and the Claude skill into ``~/.brain/`` and ``~/.claude/skills/brain/``.
        Never touches personal content (``lore/``, ``idea/``, ``research-link/``,
        ``job/``, ``followup/``, ``data/``).

        Refuses if live has live-ahead or both-changed managed files (would
        clobber unpromoted changes). Run ``status`` and ``promote`` first, or
        pass ``--force`` to override.

        With ``--with-semantic``: also creates ``<target>/.venv``, installs
        hash-pinned deps from ``requirements.txt``, audits the Nomic
        ``trust_remote_code`` files against ``scripts/nomic-trusted-revision.txt``,
        and pre-fetches the ~1.4 GB model weights so the first ``recall.py``
        call isn't a surprise download.

    python install.py audit-model
        Verify the cached Nomic remote-code SHA-256 hashes against the pinned
        values in ``scripts/nomic-trusted-revision.txt``. Exits ``2`` on
        mismatch with the full re-audit recipe printed inline. NEVER modifies
        the trusted-revision file.

    python install.py status [--json]
        Drift report: classifies each managed file as in-sync / repo-ahead /
        live-ahead / both-changed using the repo HEAD as anchor. Read-only.

    python install.py promote
        Live → repo. For each drifted managed file, shows a diff and prompts
        ``y/n/q``. Copies confirmed files into the repo working tree; never
        commits or pushes (run ``git diff && git commit`` from the repo).

    python install.py update
        ``git pull`` + refresh the live install. Refuses if the working tree
        is dirty. If ``scripts/nomic-trusted-revision.txt`` changes in the
        pull, halts with a re-audit recipe and does NOT refresh live (the
        trusted-revision file is never auto-trusted).
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
TRUSTED_REVISION_FILE = REPO_ROOT / "scripts" / "nomic-trusted-revision.txt"

TYPE_FOLDERS: tuple[str, ...] = ("lore", "idea", "research-link", "job", "followup")
OBSIDIAN_FILES: tuple[str, ...] = (
    "app.json",
    "appearance.json",
    "core-plugins.json",
    "graph.json",
)


def is_repo_root(path: Path) -> bool:
    """Sanity-check that this script is sitting inside the brain repo."""
    required = [
        path / "install.py",
        path / "SCHEMA.md",
        path / "scripts",
        path / "claude" / "skills" / "brain" / "SKILL.md",
    ]
    return all(p.exists() for p in required)


def safe_copy(src: Path, dst: Path) -> bool:
    """Copy ``src`` to ``dst`` only if content or file mode differs.

    Mode is part of the equality check so that flipping the executable bit in
    the repo (``chmod +x``) propagates to live on the next install. Without
    this, content-only equality would silently skip mode changes.

    Returns ``True`` if a write happened, ``False`` on no-op (idempotency).
    """
    if (
        dst.exists()
        and src.is_file()
        and dst.is_file()
        and filecmp.cmp(src, dst, shallow=False)
        and src.stat().st_mode == dst.stat().st_mode
    ):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copy_tree(src: Path, dst: Path, *, skip_names: set[str] | None = None) -> int:
    """Recursively copy ``src`` into ``dst``. Returns count of writes."""
    skip = skip_names or set()
    writes = 0
    for entry in sorted(src.iterdir()):
        if entry.name in skip:
            continue
        target = dst / entry.name
        if entry.is_dir():
            writes += copy_tree(entry, target, skip_names=skip)
        elif entry.is_file():
            if safe_copy(entry, target):
                writes += 1
    return writes


STALE_SCRIPT_NAMES: tuple[str, ...] = (
    # Removed in chunk 02 (ports to Python). Cleaned up on install so a layered
    # install over an older ~/.brain/ doesn't keep invoking the old .mjs files.
    "regenerate-indices.mjs",
    "normalize-source-refs.mjs",
)


def install_brain(repo: Path, target: Path) -> int:
    """Copy architecture into the brain target. Returns count of writes."""
    target.mkdir(parents=True, exist_ok=True)
    writes = 0

    writes += int(safe_copy(repo / "SCHEMA.md", target / "SCHEMA.md"))
    writes += int(safe_copy(repo / ".gitignore", target / ".gitignore"))

    for type_name in TYPE_FOLDERS:
        src = repo / type_name / "SCHEMA.md"
        if src.exists():
            (target / type_name).mkdir(parents=True, exist_ok=True)
            writes += int(safe_copy(src, target / type_name / "SCHEMA.md"))

    writes += copy_tree(
        repo / "scripts",
        target / "scripts",
        skip_names={"__pycache__"},
    )

    # Remove stale scripts that have been ported / renamed in this repo.
    scripts_dst = target / "scripts"
    for stale in STALE_SCRIPT_NAMES:
        stale_path = scripts_dst / stale
        if stale_path.is_file():
            stale_path.unlink()
            writes += 1

    obs_dst = target / ".obsidian"
    obs_dst.mkdir(parents=True, exist_ok=True)
    for fname in OBSIDIAN_FILES:
        src = repo / ".obsidian" / fname
        if src.exists() and safe_copy(src, obs_dst / fname):
            writes += 1

    return writes


def install_skill(repo: Path, target: Path) -> int:
    """Copy the Claude brain skill into the skill target. Returns count of writes."""
    src = repo / "claude" / "skills" / "brain"
    if not src.is_dir():
        raise SystemExit(f"error: missing source {src}")
    target.mkdir(parents=True, exist_ok=True)
    return copy_tree(src, target)


# --------------------------------------------------------------------------- #
# Managed-files manifest (used by status / promote)
# --------------------------------------------------------------------------- #


def iter_managed_pairs(
    repo: Path, brain_target: Path, skill_target: Path
) -> Iterator[tuple[Path, Path, str]]:
    """Yield ``(repo_path, live_path, repo_relpath)`` for every file install copies.

    ``repo_relpath`` is the POSIX-style path inside the repo (used by ``git show
    HEAD:<path>`` lookups). Skill files live under ``claude/skills/brain/`` in
    the repo but at the skill target's root in live; both paths are returned
    correctly.
    """
    yield (repo / "SCHEMA.md", brain_target / "SCHEMA.md", "SCHEMA.md")
    yield (repo / ".gitignore", brain_target / ".gitignore", ".gitignore")

    for type_name in TYPE_FOLDERS:
        src = repo / type_name / "SCHEMA.md"
        if src.exists():
            yield (src, brain_target / type_name / "SCHEMA.md", f"{type_name}/SCHEMA.md")

    scripts_root = repo / "scripts"
    for path in sorted(scripts_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(repo)
        yield (path, brain_target / rel, rel.as_posix())

    for fname in OBSIDIAN_FILES:
        src = repo / ".obsidian" / fname
        if src.exists():
            yield (src, brain_target / ".obsidian" / fname, f".obsidian/{fname}")

    skill_root = repo / "claude" / "skills" / "brain"
    for path in sorted(skill_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel_in_skill = path.relative_to(skill_root)
        yield (path, skill_target / rel_in_skill, path.relative_to(repo).as_posix())


# --------------------------------------------------------------------------- #
# status subcommand
# --------------------------------------------------------------------------- #


def _git_head_blob(repo: Path, repo_relpath: str) -> bytes | None:
    """Return file content at repo HEAD, or ``None`` if not tracked / no HEAD."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{repo_relpath}"],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _classify(
    wt_path: Path, live_path: Path, head_bytes: bytes | None
) -> str:
    """Classify a single managed file pair.

    Categories:
        - ``in-sync``: live and working tree byte-equal.
        - ``missing-in-live``: file expected from repo but absent in live.
        - ``repo-ahead``: working tree differs from HEAD; live still matches HEAD.
        - ``live-ahead``: working tree matches HEAD; live differs from HEAD.
        - ``both-changed``: both diverged from HEAD (or HEAD missing).
    """
    if not live_path.exists():
        return "missing-in-live"
    wt_bytes = wt_path.read_bytes()
    live_bytes = live_path.read_bytes()
    if wt_bytes == live_bytes:
        return "in-sync"
    if head_bytes is None:
        # Untracked at HEAD (e.g. new file in repo). Treat as repo-ahead.
        return "repo-ahead"
    wt_changed = wt_bytes != head_bytes
    live_changed = live_bytes != head_bytes
    if wt_changed and not live_changed:
        return "repo-ahead"
    if live_changed and not wt_changed:
        return "live-ahead"
    return "both-changed"


CATEGORY_ORDER = (
    "in-sync",
    "repo-ahead",
    "live-ahead",
    "both-changed",
    "missing-in-live",
)


def cmd_status(args: argparse.Namespace) -> int:
    brain_target: Path = args.target.expanduser().resolve()
    skill_target: Path = args.skill_target.expanduser().resolve()

    by_category: dict[str, list[str]] = {c: [] for c in CATEGORY_ORDER}
    for wt_path, live_path, repo_relpath in iter_managed_pairs(
        REPO_ROOT, brain_target, skill_target
    ):
        head_bytes = _git_head_blob(REPO_ROOT, repo_relpath)
        category = _classify(wt_path, live_path, head_bytes)
        by_category[category].append(repo_relpath)

    if args.json:
        payload = {
            "summary": {c: len(by_category[c]) for c in CATEGORY_ORDER},
            "files": [
                {"path": p, "category": c}
                for c in CATEGORY_ORDER
                for p in by_category[c]
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    total = sum(len(v) for v in by_category.values())
    drifted = total - len(by_category["in-sync"])
    print(f"[status] {total} managed files; {drifted} drifted from in-sync.")
    print(f"        repo: {REPO_ROOT}")
    print(f"        brain: {brain_target}")
    print(f"        skill: {skill_target}")

    in_sync_count = len(by_category["in-sync"])
    print()
    print(f"  in-sync ............ {in_sync_count}")

    for category in ("repo-ahead", "live-ahead", "both-changed", "missing-in-live"):
        files = by_category[category]
        if not files:
            continue
        print()
        print(f"  {category}: {len(files)}")
        for rel in files:
            print(f"    {rel}")

    if drifted == 0:
        print("\n[ok] in sync.")
    else:
        print(
            "\n[hint] `python install.py` updates live from repo; "
            "`python install.py promote` pushes live changes back to repo."
        )
    return 0


# --------------------------------------------------------------------------- #
# promote subcommand
# --------------------------------------------------------------------------- #


def _show_diff(live_path: Path, repo_path: Path) -> None:
    """Render a git-style unified diff showing the change live → repo."""
    color_flag = "--color=always" if sys.stdout.isatty() else "--color=never"
    subprocess.run(
        [
            "git", "diff", "--no-index", color_flag,
            str(repo_path),     # before (what repo currently has)
            str(live_path),     # after  (what we'd promote to repo)
        ],
        check=False,
    )


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "q"


def cmd_promote(args: argparse.Namespace) -> int:
    brain_target: Path = args.target.expanduser().resolve()
    skill_target: Path = args.skill_target.expanduser().resolve()

    candidates: list[tuple[Path, Path, str]] = []
    for wt_path, live_path, repo_relpath in iter_managed_pairs(
        REPO_ROOT, brain_target, skill_target
    ):
        head_bytes = _git_head_blob(REPO_ROOT, repo_relpath)
        category = _classify(wt_path, live_path, head_bytes)
        if category in ("live-ahead", "both-changed"):
            candidates.append((wt_path, live_path, repo_relpath))

    if not candidates:
        print("[promote] no live-ahead or both-changed files. Nothing to promote.")
        return 0

    print(
        f"[promote] {len(candidates)} file(s) drifted from repo. "
        "Walking through each (y=promote, n=skip, q=quit)."
    )
    promoted = 0
    skipped = 0
    quit_early = False
    for idx, (wt_path, live_path, repo_relpath) in enumerate(candidates, 1):
        print(f"\n[{idx}/{len(candidates)}] {repo_relpath}")
        _show_diff(live_path, wt_path)
        ans = _ask("Promote live -> repo? [y/n/q]: ")
        if ans == "y":
            shutil.copy2(live_path, wt_path)
            promoted += 1
            print(f"  -> copied {live_path} into {wt_path}")
        elif ans == "q":
            quit_early = True
            break
        else:
            skipped += 1
            print("  -> skipped")

    remaining = len(candidates) - promoted - skipped if quit_early else 0
    print(
        f"\n[promote] done. {promoted} promoted, {skipped} skipped"
        + (f", {remaining} not reviewed (quit)." if quit_early else ".")
    )
    if promoted > 0:
        print(
            f"\nNo commit was made. From {REPO_ROOT}, run:\n"
            "  git diff\n  git add -p && git commit\n  git push"
        )
    return 0


# --------------------------------------------------------------------------- #
# update subcommand
# --------------------------------------------------------------------------- #


def _file_sha256(path: Path) -> str:
    """Hex SHA-256 of file contents. Returns empty string if file missing."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_revision_value(path: Path) -> str:
    """Extract the ``REVISION=`` value from the trusted-revision file."""
    if not path.exists():
        return "<missing>"
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("REVISION="):
            return line.split("=", 1)[1].strip()
    return "<unknown>"


def cmd_update(args: argparse.Namespace) -> int:
    """Wrap ``git pull`` with an audit gate on the trusted-revision file.

    Refuses if the working tree is dirty. After pulling, if
    ``scripts/nomic-trusted-revision.txt`` changed, exits non-zero with a
    self-contained re-audit recipe and does NOT refresh the live install.
    Otherwise re-runs the default install path so live matches the freshly
    pulled repo.

    Never modifies the trusted-revision file.
    """
    # 1. Verify clean working tree.
    porcelain = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    if porcelain.stdout.strip():
        print(
            "[update] refusing - working tree has uncommitted changes.\n"
            "Commit or stash first. If these are live-side experiments, run\n"
            "  python install.py promote\n"
            "to walk them into the working tree, then commit from the repo\n"
            "before re-running update.",
            file=sys.stderr,
        )
        return 2

    # 2. Pre-pull state of the trusted-revision file.
    pre_hash = _file_sha256(TRUSTED_REVISION_FILE)
    pre_revision = _read_revision_value(TRUSTED_REVISION_FILE)

    # 3. git pull.
    print(f"[update] pulling {REPO_ROOT}")
    pull = subprocess.run(["git", "-C", str(REPO_ROOT), "pull"], check=False)
    if pull.returncode != 0:
        print(f"[update] git pull failed (exit {pull.returncode})", file=sys.stderr)
        return pull.returncode

    # 4. Audit gate on the trusted-revision file.
    post_hash = _file_sha256(TRUSTED_REVISION_FILE)
    post_revision = _read_revision_value(TRUSTED_REVISION_FILE)

    if pre_hash != post_hash:
        print(
            "\n[update] HALT - scripts/nomic-trusted-revision.txt was bumped upstream.\n"
            "\n"
            f"  before: {pre_revision}\n"
            f"  after:  {post_revision}\n"
            "\n"
            "This file controls which trust_remote_code .py files HuggingFace will\n"
            "execute during model load. A bump means someone updated the trusted hashes\n"
            "upstream; your install must NOT trust them automatically.\n"
            "\n"
            "Manual review steps:\n"
            "  1. Inspect the diff that landed in this pull:\n"
            f"       git -C {REPO_ROOT} log -p -1 -- scripts/nomic-trusted-revision.txt\n"
            "  2. Fetch and verify the new revision's .py files against the new hashes:\n"
            "       python install.py audit-model\n"
            "     (this downloads into ~/.cache/huggingface and checks SHA-256; it\n"
            "     fails loud if anything is off)\n"
            "  3. Read the cached .py files for the new revision and confirm they\n"
            "     don't do anything surprising (the audit checklist is in the\n"
            "     trusted-revision file itself).\n"
            "  4. If clean, re-run `python install.py update`. If anything is\n"
            "     suspicious, `git revert` the bump locally and stop here.\n"
            "\n"
            "Live ~/.brain/ was NOT refreshed. The trusted-revision file was NOT\n"
            "modified by this command.",
            file=sys.stderr,
        )
        return 2

    # 5. Refresh live install.
    print("[update] no trusted-revision change. Refreshing install.")
    return cmd_install(args)


# --------------------------------------------------------------------------- #
# Semantic install path
# --------------------------------------------------------------------------- #


def resolve_venv_path(target: Path) -> Path:
    """Resolve the venv root, matching the same logic the in-brain scripts use.

    Order: ``BRAIN_VENV`` env var (root or python binary) > ``<target>/.venv``.
    Returns the venv ROOT directory (not the python binary).
    """
    override = os.environ.get("BRAIN_VENV")
    if override:
        p = Path(override).expanduser()
        if p.is_file():
            # User pointed at the python binary directly; walk up to root.
            return p.parent.parent
        return p
    return target / ".venv"


def install_semantic(target: Path) -> int:
    """Create the venv, install hash-pinned deps, audit, and warm up.

    Exits the process non-zero on any failure. Returns 0 on success.
    """
    if not REQUIREMENTS_FILE.exists():
        print(f"error: missing {REQUIREMENTS_FILE}", file=sys.stderr)
        return 2

    venv_root = resolve_venv_path(target)
    venv_python = venv_root / "bin" / "python"

    # 1. Create venv if missing
    if not venv_python.exists():
        print(f"[venv] creating {venv_root}")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_root)],
            check=True,
        )
    else:
        print(f"[venv] reusing {venv_root}")

    # 2. Install hash-pinned deps
    print(f"[deps] installing from {REQUIREMENTS_FILE.name} (--require-hashes)")
    subprocess.run(
        [
            str(venv_python), "-m", "pip", "install",
            "--require-hashes",
            "--disable-pip-version-check",
            "-r", str(REQUIREMENTS_FILE),
        ],
        check=True,
    )

    # 3. Audit + warm-up: run inside the venv (where torch/sentence_transformers live).
    #    Uses scripts/_warmup.py which was just copied into <target>/scripts/.
    scripts_dir = target / "scripts"
    warmup_script = scripts_dir / "_warmup.py"
    if not warmup_script.exists():
        print(f"error: missing {warmup_script}", file=sys.stderr)
        return 2
    subprocess.run([str(venv_python), str(warmup_script)], check=True, cwd=str(scripts_dir))

    print("[ok] semantic install complete")
    return 0


# --------------------------------------------------------------------------- #
# audit-model subcommand
# --------------------------------------------------------------------------- #


def cmd_audit_model() -> int:
    """Verify Nomic remote-code SHA-256 hashes against the pinned values.

    Exits ``2`` on mismatch with a self-contained re-audit recipe. Never
    downloads, never modifies ``nomic-trusted-revision.txt``.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import _nomic  # type: ignore[import-not-found]

    if not TRUSTED_REVISION_FILE.exists():
        print(f"error: missing {TRUSTED_REVISION_FILE}", file=sys.stderr)
        return 2

    cfg = _nomic.read_revision_config(TRUSTED_REVISION_FILE)
    cache_dir = _nomic.compute_cache_dir(cfg)

    if not cache_dir.exists():
        print(
            f"[audit-model] no cached snapshot at {cache_dir}\n"
            "Run `python install.py --with-semantic` first to fetch the pinned revision.",
            file=sys.stderr,
        )
        return 2

    mismatches = _nomic.check_remote_code_hashes(cfg, cache_dir)
    if not mismatches:
        revision = cfg["REVISION"]
        print(
            f"[audit-model] OK - revision {revision[:12]} hashes match "
            f"(audited {cfg.get('AUDITED_AT', '?')} by {cfg.get('AUDITED_BY', '?')})."
        )
        return 0

    print(
        "[audit-model] HASH MISMATCH - Nomic remote-code files do not match the audited revision.",
        file=sys.stderr,
    )
    print("\nMismatched files:", file=sys.stderr)
    for m in mismatches:
        # Render path with ~ for readability.
        try:
            display_path = "~/" + str(m.path.relative_to(Path.home()))
        except ValueError:
            display_path = str(m.path)
        print(f"  {m.fname}", file=sys.stderr)
        print(f"    path:     {display_path}", file=sys.stderr)
        print(f"    expected: {m.expected}", file=sys.stderr)
        print(f"    actual:   {m.actual}", file=sys.stderr)

    print(
        "\nTo re-audit (manual review required, never automated):\n"
        "  1. Open scripts/nomic-trusted-revision.txt; bump REVISION to a new commit\n"
        "     from https://huggingface.co/nomic-ai/nomic-bert-2048/commits/main\n"
        "  2. Run `python install.py --with-semantic` - it will fail-loud with new hashes\n"
        "  3. Manually read the cached .py files in the snapshot dir\n"
        "  4. If clean, paste the new hashes into nomic-trusted-revision.txt\n"
        "\nThe trusted-revision file is NEVER auto-updated. Human review is the security control.",
        file=sys.stderr,
    )
    return 2


# --------------------------------------------------------------------------- #
# default install subcommand
# --------------------------------------------------------------------------- #


def _detect_unsafe_overwrite(
    brain_target: Path, skill_target: Path
) -> list[tuple[str, str]]:
    """Return ``(category, repo_relpath)`` tuples for files install would clobber.

    Walks the managed-files manifest and classifies each pair. Returns entries
    classified as ``live-ahead`` or ``both-changed`` - those are the cases
    where install would overwrite live changes that haven't been promoted to
    the repo. Empty list = safe to install.

    The ``repo-ahead``, ``in-sync``, and ``missing-in-live`` categories are
    explicitly OK: they represent the install's normal operating modes.
    """
    unsafe: list[tuple[str, str]] = []
    for wt_path, live_path, repo_relpath in iter_managed_pairs(
        REPO_ROOT, brain_target, skill_target
    ):
        head_bytes = _git_head_blob(REPO_ROOT, repo_relpath)
        category = _classify(wt_path, live_path, head_bytes)
        if category in ("live-ahead", "both-changed"):
            unsafe.append((category, repo_relpath))
    return unsafe


def cmd_install(args: argparse.Namespace) -> int:
    target: Path = args.target.expanduser().resolve()
    skill_target: Path = args.skill_target.expanduser().resolve()

    if not getattr(args, "force", False):
        unsafe = _detect_unsafe_overwrite(target, skill_target)
        if unsafe:
            print(
                f"[install] refusing - {len(unsafe)} file(s) in live have changes "
                "that would be overwritten:",
                file=sys.stderr,
            )
            by_cat: dict[str, list[str]] = {}
            for cat, rel in unsafe:
                by_cat.setdefault(cat, []).append(rel)
            for cat in ("live-ahead", "both-changed"):
                files = by_cat.get(cat, [])
                if files:
                    print(f"\n  {cat}: {len(files)}", file=sys.stderr)
                    for rel in files:
                        print(f"    {rel}", file=sys.stderr)
            print(
                "\nNext step:\n"
                "  python install.py promote   # walk live changes, copy approved ones into repo\n"
                f"  cd {REPO_ROOT} && git diff && git commit\n"
                "  python install.py           # re-run; will be safe now\n"
                "\nOr to overwrite live anyway: python install.py --force\n"
                "(Live changes will remain in ~/.brain/.git history if they were committed there.)",
                file=sys.stderr,
            )
            return 2

    print(f"[brain] installing architecture into {target}")
    brain_writes = install_brain(REPO_ROOT, target)
    print(f"[brain] {brain_writes} file(s) written")

    print(f"[skill] installing Claude skill into {skill_target}")
    skill_writes = install_skill(REPO_ROOT, skill_target)
    print(f"[skill] {skill_writes} file(s) written")

    if brain_writes == 0 and skill_writes == 0:
        print("[ok] already in sync (idempotent re-run)")
    else:
        print("[ok] install complete")

    if args.with_semantic:
        return install_semantic(target)
    return 0


def main() -> int:
    # Line-buffer stdout so our prints interleave correctly with subprocess
    # output (pip / warm-up) when piped to a file or another tool.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    parser = argparse.ArgumentParser(
        prog="install.py",
        description="Bootstrap install for the brain.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".brain",
        help="Brain install location (default: ~/.brain).",
    )
    parser.add_argument(
        "--skill-target",
        type=Path,
        default=Path.home() / ".claude" / "skills" / "brain",
        help="Claude skill install location (default: ~/.claude/skills/brain).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Skip the safety check that refuses to overwrite live-ahead or "
            "both-changed files. Use only when you mean to clobber live changes."
        ),
    )
    parser.add_argument(
        "--with-semantic",
        action="store_true",
        help=(
            "After the default install, create the Python venv, install hash-pinned "
            "deps, audit Nomic trust_remote_code files, and pre-fetch the ~1.4 GB "
            "model weights."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "audit-model",
        help=(
            "Verify cached Nomic remote-code SHA-256 hashes against pinned values. "
            "Never downloads, never modifies the trusted-revision file."
        ),
    )
    status_p = subparsers.add_parser(
        "status",
        help="Drift report: classify each managed file as in-sync / repo-ahead / live-ahead / both-changed.",
    )
    status_p.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON output.",
    )
    subparsers.add_parser(
        "promote",
        help=(
            "Live → repo. Per-file diff + y/n/q prompt. Copies confirmed files "
            "into the repo working tree; never commits or pushes."
        ),
    )
    subparsers.add_parser(
        "update",
        help=(
            "git pull + refresh the live install. Refuses if the working tree "
            "is dirty. Halts with a re-audit recipe if scripts/nomic-trusted-revision.txt "
            "changes in the pull."
        ),
    )

    args = parser.parse_args()

    if not is_repo_root(REPO_ROOT):
        print(
            f"error: install.py must be run from inside the brain repo "
            f"(missing expected files under {REPO_ROOT}).",
            file=sys.stderr,
        )
        return 2

    if args.command == "audit-model":
        return cmd_audit_model()
    if args.command == "status":
        return cmd_status(args)
    if args.command == "promote":
        return cmd_promote(args)
    if args.command == "update":
        return cmd_update(args)
    return cmd_install(args)


if __name__ == "__main__":
    raise SystemExit(main())
