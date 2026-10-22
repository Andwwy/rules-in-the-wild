"""`enforce install NAME`: tested recipes, pinned versions, each ending with a smoke test (README: Install).

A recipe is one of:
  pip   a virtual environment of its own, with these packages; its programs are linked into TOOLS_BIN, and its Python
        is TOOLS_DIR/<name>/bin/python (for a library such as jsonschema)
  npm   these packages, with Node (the recipe `node` first); their programs are linked into TOOLS_BIN
  url   a download: a tarball (unpacked) or one program; the named programs are linked into TOOLS_BIN
  apt   Debian packages (pinned by the image's Debian release); their programs are already on PATH
  rustup  a Rust toolchain of this version (minimal profile); cargo and rustc are linked into TOOLS_BIN
  cargo   these crates, built with `cargo install --locked` (the recipe `rust` first)
`needs` names recipes that must be installed first. Everything goes into TOOLS_DIR/<name>; TOOLS_BIN is made readable
for every user, and is the folder to put on PATH (or call a program by its full path).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(os.environ.get("ENFORCE_ROOT", "/opt/enforce")) / "tool-installs"
TOOLS_BIN = TOOLS_DIR / "bin"

NODE = "22.23.3"
# Versions as in the enforcer notes (prompts/guides/enforcers.md, checked on 2026-10-17), so a note and a recipe agree.
RECIPES: dict[str, dict] = {
    # code scans, schemas, syntax trees
    "semgrep": {"about": "Semgrep 1.177.0: pattern-based code scans", "pip": ["semgrep==1.177.0"],
                "bin": ["semgrep"], "smoke": ["semgrep", "--version"]},
    "jsonschema": {"about": "jsonschema 4.23.0: JSON Schema validation in Python (tool-installs/jsonschema/bin/python)",
                   "pip": ["jsonschema==4.23.0"], "smoke_import": "jsonschema"},
    "js-parser": {"about": "tree-sitter 0.24.0 with the JavaScript 0.23.1 and TypeScript 0.23.2 grammars: "
                           "JS/TS syntax trees in Python (tool-installs/js-parser/bin/python)", "pip": ["tree-sitter==0.24.0", "tree-sitter-javascript==0.23.1",
                                           "tree-sitter-typescript==0.23.2"], "smoke_import": "tree_sitter_javascript"},
    # Python tools
    "ruff": {"about": "Ruff 0.17.1: Python linter and formatter", "pip": ["ruff==0.17.1"], "bin": ["ruff"],
             "smoke": ["ruff", "--version"]},
    "shellcheck": {"about": "ShellCheck (shellcheck-py 0.11.0.1): shell script linter", "pip": ["shellcheck-py==0.11.0.1"],
                   "bin": ["shellcheck"], "smoke": ["shellcheck", "--version"]},
    "yamllint": {"about": "yamllint 1.38.0: YAML linter", "pip": ["yamllint==1.38.0"], "bin": ["yamllint"],
                 "smoke": ["yamllint", "--version"]},
    "pytest": {"about": "pytest 9.1.1: Python test runner (the project's own packages are not in its environment)",
               "pip": ["pytest==9.1.1"], "bin": ["pytest"], "smoke": ["pytest", "--version"]},
    "openapi": {"about": "openapi-spec-validator 0.9.0: OpenAPI document validator", "pip": ["openapi-spec-validator==0.9.0"],
                "bin": ["openapi-spec-validator"], "smoke": ["openapi-spec-validator", "--help"]},
    "pre-commit": {"about": "pre-commit 4.7.0: git pre-commit hook framework (its hooks fetch their tools on first use)",
                   "pip": ["pre-commit==4.7.0"], "bin": ["pre-commit"], "needs": ["git"],
                   "smoke": ["pre-commit", "--version"]},
    # Node and JS tools
    "node": {"about": f"Node.js {NODE} with npm", "url": f"https://nodejs.org/dist/v{NODE}/node-v{NODE}-linux-x64.tar.gz",
             "bin": ["bin/node", "bin/npm", "bin/npx"], "smoke": ["node", "--version"]},
    "eslint": {"about": "ESLint 10.13.0: JavaScript / TypeScript linter", "npm": ["eslint@10.13.0"], "bin": ["eslint"],
               "smoke": ["eslint", "--version"]},
    "stylelint": {"about": "Stylelint 17.16.0: CSS linter", "npm": ["stylelint@17.16.0"], "bin": ["stylelint"],
                  "smoke": ["stylelint", "--version"]},
    "biome": {"about": "Biome 2.5.15: web linter and formatter", "npm": ["@biomejs/biome@2.5.15"], "bin": ["biome"],
              "smoke": ["biome", "--version"]},
    "typescript": {"about": "TypeScript 7.0.2: tsc, the type checker and compiler", "npm": ["typescript@7.0.2"],
                   "bin": ["tsc"], "smoke": ["tsc", "--version"]},
    "jest": {"about": "Jest 30.5.2: JavaScript test runner", "npm": ["jest@30.5.2"], "bin": ["jest"],
             "smoke": ["jest", "--version"]},
    "ajv": {"about": "ajv-cli 5.0.0: JSON Schema validator", "npm": ["ajv-cli@5.0.0"], "bin": ["ajv"],
            "smoke": ["ajv", "help"]},
    "markdownlint": {"about": "markdownlint-cli2 0.23.3: Markdown linter", "npm": ["markdownlint-cli2@0.23.3"],
                     "bin": ["markdownlint-cli2"],
                     "smoke": ["sh", "-c", "printf '# Title\\n' > /tmp/smoke.md && markdownlint-cli2 /tmp/smoke.md"]},
    "remark-lint": {"about": "remark-cli 12.0.1, remark-lint 10.0.1, remark-preset-lint-recommended 7.0.1: Markdown "
                             "linter", "npm": ["remark-cli@12.0.1", "remark-lint@10.0.1",
                                              "remark-preset-lint-recommended@7.0.1"], "bin": ["remark"],
                    "smoke": ["remark", "--version"]},
    "commitlint": {"about": "commitlint 21.2.3 with config-conventional 21.2.3: commit message linter",
                   "npm": ["@commitlint/cli@21.2.3", "@commitlint/config-conventional@21.2.3"], "bin": ["commitlint"],
                   "smoke": ["commitlint", "--version"]},
    "pnpm": {"about": "pnpm 12.14.0: Node package manager", "npm": ["pnpm@12.14.0"], "bin": ["pnpm"],
             "smoke": ["pnpm", "--version"]},
    # other programs
    "vale": {"about": "Vale 3.24.0: prose linter", "url": "https://github.com/vale-cli/vale/releases/download/v3.24.0/"
             "vale_3.24.0_Linux_64-bit.tar.gz", "bin": ["vale"], "smoke": ["vale", "--version"]},
    "git": {"about": "git (Debian 12)", "apt": ["git"], "smoke": ["git", "--version"]},
    "jq": {"about": "jq (Debian 12): JSON processor", "apt": ["jq"], "smoke": ["jq", "--version"]},
    "ripgrep": {"about": "ripgrep (Debian 12): rg, a fast grep", "apt": ["ripgrep"], "smoke": ["rg", "--version"]},
    "curl": {"about": "curl (Debian 12): HTTP client", "apt": ["curl"], "smoke": ["curl", "--version"]},
    "inotify-tools": {"about": "inotify-tools (Debian 12): inotifywait, which reports file changes as they happen",
                      "apt": ["inotify-tools"], "smoke": ["inotifywait", "--help"], "smoke_exit": [0, 1]},
    "gcc": {"about": "gcc and the C library headers (Debian 12): the linker that Rust needs", "apt": ["gcc", "libc6-dev"],
            "smoke": ["gcc", "--version"]},
    "rust": {"about": "Rust 1.99.1 (minimal): cargo and rustc, to build Rust tools", "rustup": "1.99.1",
             "needs": ["gcc"], "smoke": ["cargo", "--version"]},
    "dogwood": {"about": "Dogwood CLI 1.1.0: policies on agent actions that depend on what happened before, and when "
                         "(Cedar-based; `dogwood replay`)", "cargo": ["dogwood-cli@1.1.0"], "bin": ["dogwood"],
                "smoke": ["dogwood", "--help"]},
    "opa": {"about": "Open Policy Agent 1.0.0: policies in Rego, evaluated with `opa eval`",
            "url": "https://github.com/open-policy-agent/opa/releases/download/v1.0.0/opa_linux_amd64_static",
            "bin": ["opa"], "smoke": ["opa", "version"]},
}

ALLOW = Path(__file__).with_name("recipes.allow")      # when the toolbox is a route's share: only the recipes it names
if ALLOW.exists():
    RECIPES = {k: v for k, v in RECIPES.items() if k in ALLOW.read_text().split()}


def env() -> dict:
    """The environment that installed programs run in: TOOLS_BIN first on PATH."""
    return {**os.environ, "PATH": f"{TOOLS_BIN}:{os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}",
            "DEBIAN_FRONTEND": "noninteractive"}


def sh(cmd: list[str], ok: tuple[int, ...] = (0,), **kw) -> None:
    kw.setdefault("env", env())
    done = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if done.returncode not in ok:
        raise SystemExit(f"failed: {' '.join(cmd)}\n{(done.stderr or done.stdout)[-1500:]}")


def link(target: Path, name: str) -> None:
    TOOLS_BIN.mkdir(parents=True, exist_ok=True)
    dest = TOOLS_BIN / name
    if dest.is_symlink() or dest.exists():
        dest.unlink()
    dest.symlink_to(target)


def installed(name: str) -> bool:
    return (TOOLS_DIR / name / ".installed").exists()


def install(name: str, quiet: bool = False) -> int:
    if name not in RECIPES:
        print(f"no recipe {name!r}; the recipes: {', '.join(RECIPES)}. Other tools: install them yourself "
              f"(catalog/enforcers.md says how, per leaf)", file=sys.stderr)
        return 1
    r, dest = RECIPES[name], TOOLS_DIR / name
    for dep in r.get("needs", []) + (["node"] if "npm" in r else []) + (["rust"] if "cargo" in r else []):
        if not installed(dep) and install(dep, quiet=True):
            return 1
    if not quiet or not installed(name):
        print(f"installing {r['about']} into {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    if "pip" in r:
        sh([sys.executable, "-m", "venv", str(dest)])
        sh([str(dest / "bin" / "pip"), "install", "-q", "--disable-pip-version-check", *r["pip"]])
        for b in r.get("bin", []):
            link(dest / "bin" / b, b)
        if "smoke_import" in r:
            sh([str(dest / "bin" / "python"), "-c", f"import {r['smoke_import']}"])
    elif "npm" in r:
        sh([str(TOOLS_BIN / "npm"), "install", "--prefix", str(dest), "--no-audit", "--no-fund", "--loglevel=error",
            *r["npm"]])
        for b in r.get("bin", []):
            link(dest / "node_modules" / ".bin" / b, b)
    elif "url" in r:
        tarball = r["url"].endswith((".tar.gz", ".tgz"))
        file = dest / (Path(r["url"]).name if tarball else r["bin"][0])        # one program: saved under its name
        urllib.request.urlretrieve(r["url"], file)
        if tarball:
            with tarfile.open(file) as t:
                top = os.path.commonpath(t.getnames())
                t.extractall(dest, filter="tar")
            file.unlink()
            base = dest / top if top and (dest / top).is_dir() else dest
        else:
            file.chmod(0o755)
            base = dest
        for b in r.get("bin", []):
            link(base / b, Path(b).name)
    elif "rustup" in r:
        init = dest / "rustup-init"
        urllib.request.urlretrieve("https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init", init)
        init.chmod(0o755)
        homes = {"RUSTUP_HOME": str(dest / "rustup"), "CARGO_HOME": str(dest / "cargo")}
        sh([str(init), "-y", "--profile", "minimal", "--default-toolchain", r["rustup"], "--no-modify-path"],
           env={**env(), **homes})
        toolchain = next((dest / "rustup" / "toolchains").glob(f"{r['rustup']}-*")) / "bin"
        for b in ("cargo", "rustc"):                         # the real programs, not rustup's proxies
            link(toolchain / b, b)
    elif "cargo" in r:
        sh([str(TOOLS_BIN / "cargo"), "install", "--locked", "--quiet", "--root", str(dest), *r["cargo"]],
           env={**env(), "CARGO_HOME": str(dest / "cargo-home")})
        shutil.rmtree(dest / "cargo-home", ignore_errors=True)    # the downloaded sources: not needed to run
        for b in r.get("bin", []):
            link(dest / "bin" / b, b)
    elif "apt" in r:
        sh(["apt-get", "update", "-q"])
        sh(["apt-get", "install", "-y", "-q", "--no-install-recommends", *r["apt"]])
    if "smoke" in r:
        sh(r["smoke"], ok=tuple(r.get("smoke_exit", [0])))
    sh(["chmod", "-R", "a+rX", str(TOOLS_DIR)])                # every user can run them (the agent too)
    (dest / ".installed").write_text(r["about"] + "\n")
    if not quiet:
        print(f"ok: {name} installed")
    return 0


def describe() -> str:
    return "\n".join(f"  {k:<14} {v['about']}" + (" (installed)" if installed(k) else "") for k, v in RECIPES.items())


def which(program: str) -> str | None:
    return shutil.which(program, path=env()["PATH"])
