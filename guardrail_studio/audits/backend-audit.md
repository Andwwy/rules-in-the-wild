# Audit of the four remaining Studio generator backends

Audit date: 2026-10-27. Scope: the implemented Regex, JSON Schema, Path/manifest, and Semgrep backends. The full 30-leaf taxonomy was not assessed. This audit changes no production backend behavior. Evidence is in `backend-probes.json`; the executable wrapper probes are in `probe_backends.py` (the staged-snapshot probe was run separately and appended).

## Finding summary

| Backend | Finding | Recommended direction |
| --- | --- | --- |
| Path/manifest | Same structural problem as the former Git-diff backend: the generated object has only required and forbidden globs. | Generate a real Python/pathlib check (or pytest tests over a declared manifest). Keep simple globs as a convenience, not the capability ceiling. |
| Semgrep | Already uses native rule patterns and the real engine, but our top-level field allowlist blocks valid native rules. | Emit a native rules file and validate with the supported Semgrep engine; permit supported native fields with clearly bounded engine requirements. |
| Regex/literal | Uses native Python regex syntax, but only one whole-file search with require/forbid semantics; file scope is mandatory. | Keep Python re as the target. Separate reusable text predicates from file binding; make search/fullmatch/per-line semantics explicit and support composition where necessary. |
| JSON Schema | Already accepts native Draft 2020-12 schemas and unbound document checks. | Keep this backend. Export the standalone schema, add appropriate parsers and declared dependency handling where needed. |

## P1: Path/manifest has an artificial capability ceiling

Code: `catalog.py` config allows only required/forbidden lists. `guardrail.py` evaluates each required glob existentially over the collected file paths.

Confirmed probes:

- `required: ["services/*/Dockerfile"]` passes when `services/api/Dockerfile` exists and `services/web/package.json` exists with no web Dockerfile. This is a tempting but invalid translation of **every** service having a Dockerfile. We constructed this approximation to probe expressiveness; we did not observe Codex generate it in this audit.
- A real empty `docs/` directory is not in the collected manifest; a directory-existence check fails even though the directory exists.
- The repository collector skips symlinks and represents only files. Directory kinds, symlink requirements, counts, per-directory quantification, and filename-to-directory correspondence are not represented by the current config.

The replacement needs a declared manifest contract (paths, entry types, and any required link metadata) and executable predicates, rather than another growing list of bespoke policy fields. A generated pathlib function or pytest test is a concrete implementation target; there is no established path-specific framework verified by this audit that we can claim substitutes for all of these policies. Runtime write prevention remains a separate enforcement point.

## P1: Semgrep native fields are rejected before the engine sees them

Code: `guardrail.py:55` permits only id/message/languages/severity and one search-pattern operator at the top level.

Confirmed with the installed Semgrep engine:

- A Python eval rule with native `paths.include: ["src/**"]` is rejected by Studio. Scanning it directly finds the violation under src and excludes the same pattern under tests.
- A native taint rule with explicit `mode`, `pattern-sources`, `pattern-sinks`, and `pattern-sanitizers` is rejected by Studio. Direct execution identifies one unsanitized flow and accepts the sanitized one.

This is partial native-rule support, not a wholly custom rule language. Nested search operators already pass through. The change should preserve native supported syntax instead of indiscriminately enabling every Semgrep feature: engine/edition/version requirements, scan skips, and relevant errors must stay explicit. In particular, the audit does not establish whole-program or interfile coverage.

Native references: [rule syntax](https://docs.semgrep.dev/writing-rules/rule-syntax), [taint overview](https://docs.semgrep.dev/writing-rules/data-flow/taint-mode/overview).

## P2: Regex needs explicit predicate semantics and independent input binding

Code: `guardrail.py:91` always uses `re.MULTILINE` and `pattern.search(content)`. `catalog.py` rejects null scope for Regex.

Confirmed probes:

- With require mode, `^[a-z]+$` passes the file `valid\nINVALID`, because one line matches. This does not prove Codex generated the wrong pattern: absolute anchors or a forbidden-invalid pattern can express an entire-value constraint. It demonstrates that the interface must distinguish match/search and whole-value/per-line intent.
- A standalone regex predicate cannot have null scope, although generating it need not establish repository paths. This is the same generation-vs-application scope problem already fixed for JSON Schema.

Recommended output: a native pattern plus explicit matching semantics (or a small Python re predicate), text-input testing, and optional file binding. Keep the engine/dialect explicit. PDF extraction, YAML parsing, and structured field selection are input adapters; a regex by itself does not supply them. Source/AST obligations should not be forced into Regex just to improve assignment coverage.

Reference: [Python re](https://docs.python.org/3/library/re.html).

## JSON Schema does not need the Git-diff replacement

`config.schema` already accepts the native schema vocabulary rather than a fixed list of application policy fields. `Draft202012Validator` executes it. The explicit document path already works without repository scope.

Confirmed probe: a native `oneOf`/`not` schema accepts either removal method alone and rejects both/neither. No new custom capability flag is needed.

Remaining work is packaging and input integration:

- Export `schema.json` directly, instead of only nesting it inside guardrail.json.
- YAML/JSONL require parsing/record iteration before schema validation; the current file runner calls json.loads on a complete file only.
- References outside the schema are explicitly disallowed. Referenced contracts must be supplied/bundled, not invented; that limitation should be distinguished from the schema language's own capability.
- The implementation deliberately selects Draft 2020-12. Other schema drafts and format-support dependencies must be declared if added.

References: [JSON Schema](https://json-schema.org/learn/getting-started-step-by-step), [python-jsonschema](https://python-jsonschema.readthedocs.io/en/stable/validate/).

## Shared P1: Runnable checks still lack local gate integration

All four bundles contain only guardrail.json, guardrail.py, spec.schema.json, requirements.txt, and README.md. Unlike the new Danger output, none includes a hook installer or a pre-commit configuration. Their CLI exit code can be wired into a gate, but Studio has not done so.

A hook must also inspect the right snapshot. Confirmed on a temporary real Git repository: stage README.md containing TODO, then remove TODO only in the worktree. The current `--repo` regex runner passes, while `git show :README.md` still contains TODO. Merely putting that command in pre-commit would validate the wrong version.

Recommended shared application adapter: select full worktree vs staged snapshot explicitly; validate staged contents for a commit gate, handle deleted files and repository-wide path obligations deliberately, and preserve existing hooks. Do not claim that a successful worktree scan enforces the proposed commit. [pre-commit](https://pre-commit.com/) is an available integration framework; it is not a substitute for choosing the right checker and input snapshot.

## Suggested order

1. Replace the path predicate ceiling and remove the Semgrep native-syntax restrictions.
2. Export native artifacts (Semgrep rule file, JSON schema, Python checks) and add a shared local application/hook adapter with staged-snapshot behavior.
3. Improve Regex matching modes and standalone text input; add document preprocessing only where source rules require it.

These are implementation findings, not a measured failure rate on the classified clauses and not proof that the resulting generated checks are semantically faithful.
