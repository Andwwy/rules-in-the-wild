-- =============================================================================
-- Rules-in-the-Wild — DuckDB / MotherDuck schema (v0.3, 2026-05-19)
--
-- Pipeline (matches the architecture diagram):
--   Crawler → rules_file → rule → rule_llm_decision → rule_classification_current
--                                         ↕                       ↑
--                                  rule_human_label  ──────────────┘
--                                         │
--                                         └→ rule_semantic_cluster (dup-by-meaning)
--
-- The canonical schema doc is `Design docs/SCHEMA-REDESIGN.md` (v0.3 changes)
-- and `Design docs/DESIGN.md` §2.2 (overall design). The Postgres flavour for
-- reference lives in `Design docs/schema.sql`.
--
-- Two requirements drive the v0.3 shape:
--   1. A "rules file" is a *complete* agent rules file (CLAUDE.md, AGENTS.md,
--      .cursorrules, .windsurfrules, …). Renamed source_file → rules_file.
--   2. Every LLM judge decision is *recorded* (append-only history per rule),
--      with prompt + raw response stored verbatim so the labeling UI can show
--      "what the model saw, what it actually said" for any past decision.
--      Dropped the previous UNIQUE(rule_id, model, prompt_version).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Enumerated taxonomy types
-- -----------------------------------------------------------------------------

CREATE TYPE rule_specificity     AS ENUM ('universal','stack_specific','project_specific');
CREATE TYPE rule_cognitive_load  AS ENUM ('zero_lookup','requires_reading_file','requires_running_cmd','requires_external_state');
CREATE TYPE rule_constraint_level AS ENUM ('planning_reasoning','output_content','tool_use','human_workflow','agent_human_interaction');
CREATE TYPE enforcement_mechanism AS ENUM ('deterministic','llm_judge','hybrid','human_remind');
CREATE TYPE enforcement_scope     AS ENUM ('local','full_repo','runtime_external');
CREATE TYPE enforcement_trigger   AS ENUM ('session_init','settings_json','pre_tool_verify_gate','intermediate_output','post_exec','final_output');
CREATE TYPE rule_kind             AS ENUM (
    'repository_architectural','repository_conventions','repository_ui','repository_language',
    'process_agent_response','process_context_chasing','process_sequential'
);
CREATE TYPE artifact_required AS ENUM (
    'reasoning_trace','output','code_diff','ui_snapshot','agent_plan','tool_call_log'
);

-- "Rules file" = complete agent rules file. Every value is a recognised
-- filename / directory convention for instructing an LLM coding agent.
CREATE TYPE rules_file_kind AS ENUM (
    'claude_md',                   -- CLAUDE.md, .claude/*.md
    'agents_md',                   -- AGENTS.md
    'cursor_rules',                -- .cursorrules, .cursor/rules/*.mdc
    'windsurf_rules',              -- .windsurfrules
    'aider_conventions',           -- CONVENTIONS.md, .aider.conf.yml
    'cline_rules',                 -- .clinerules
    'copilot_instructions',        -- .github/copilot-instructions.md
    'continue_rules',              -- .continue/rules
    'llms_txt',                    -- llms.txt
    'system_prompt_repo',          -- x1xhlol/system-prompts-and-models-of-ai-tools etc.
    'awesome_list',                -- curated lists
    'vendor_doc',                  -- anthropic.com / openai.com Model Spec etc.
    -- Claude Code marketplace plugins. A marketplace is a Git repo containing
    -- .claude-plugin/marketplace.json listing plugins; each plugin contributes
    -- instruction-bearing files. Discovered via trending search the same way
    -- AGENTS.md/CLAUDE.md are — never via a fixed seed list.
    'claude_marketplace_manifest', -- .claude-plugin/marketplace.json (evidence only, not extracted)
    'claude_plugin_manifest',      -- .claude-plugin/plugin.json (evidence only, not extracted)
    'claude_plugin_command',       -- commands/*.md inside a plugin
    'claude_plugin_agent',         -- agents/*.md inside a plugin
    'claude_plugin_skill',         -- skills/<name>/SKILL.md inside a plugin
    'claude_plugin_hook_config',   -- hooks/hooks.json (evidence only, not extracted)
    'other'
);

CREATE TYPE ingestion_status AS ENUM ('queued','running','succeeded','failed','partial');

-- New for v0.3 ↓
CREATE TYPE judge_decision_trigger AS ENUM (
    'initial',             -- first classification at extract-time
    'prompt_revised',      -- judge prompt template was bumped → batch rerun
    'human_disagreed',     -- a human marked the previous decision wrong
    'manual_rerun'         -- operator-initiated
);

CREATE TYPE human_label_disposition AS ENUM (
    'confirmed_llm',       -- agrees with the LLM verbatim
    'revised_llm',         -- changed >=1 axis
    'rejected',            -- not a real rule (extractor noise — file path, sentence fragment)
    'marked_duplicate'     -- semantic dup of another rule
);

CREATE TYPE semantic_cluster_method AS ENUM (
    'embedding_threshold', -- automated cosine >= threshold
    'llm_pair_judge',      -- pair-judge LLM said "same rule"
    'human_merge'          -- human marked 'marked_duplicate'
);

-- -----------------------------------------------------------------------------
-- 2. Source provenance
-- -----------------------------------------------------------------------------

CREATE TABLE source_project (
    id              UUID PRIMARY KEY DEFAULT uuid(),
    host            TEXT NOT NULL,                  -- 'github.com', 'defi_claude_marketplace', ...
    owner           TEXT NOT NULL,
    name            TEXT NOT NULL,
    canonical_url   TEXT NOT NULL UNIQUE,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_crawled_at TIMESTAMPTZ
);

-- The complete agent rules file. raw_content is the LLM judge's
-- "Look at context" arrow — the judge sees the rule text PLUS the whole file.
CREATE TABLE rules_file (
    id              UUID PRIMARY KEY DEFAULT uuid(),
    project_id      UUID NOT NULL REFERENCES source_project(id),
    path            TEXT NOT NULL,                   -- e.g. 'CLAUDE.md', '.cursor/rules/python.mdc'
    kind            rules_file_kind NOT NULL,
    commit_sha      TEXT,
    raw_content     TEXT NOT NULL,                   -- full md, judge context
    content_sha256  BLOB NOT NULL,                   -- exact-file-dedup key
    byte_size       INTEGER NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, path, commit_sha)
);
CREATE INDEX rules_file_project_idx ON rules_file (project_id);
CREATE INDEX rules_file_sha_idx     ON rules_file (content_sha256);

-- -----------------------------------------------------------------------------
-- 3. Raw rule  (one extracted directive)
-- -----------------------------------------------------------------------------

CREATE TABLE rule (
    id                UUID PRIMARY KEY DEFAULT uuid(),
    rules_file_id     UUID NOT NULL REFERENCES rules_file(id),
    rule_text         TEXT NOT NULL,                 -- as written
    rule_text_norm    TEXT NOT NULL,                 -- lowercase + whitespace-collapsed
    rule_text_sha256  BLOB NOT NULL,                 -- exact-match dedup key
    section_anchor    TEXT,                          -- containing heading
    line_start        INTEGER NOT NULL,
    line_end          INTEGER NOT NULL,
    embedding         FLOAT[1024],                   -- 1024-d, Perplexity now / Voyage-3 pre-prod
    extracted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    extractor_version TEXT NOT NULL,
    UNIQUE (rules_file_id, line_start, line_end)
);
CREATE INDEX rule_sha_idx        ON rule (rule_text_sha256);
CREATE INDEX rule_rules_file_idx ON rule (rules_file_id);

-- -----------------------------------------------------------------------------
-- 4. LLM judge decisions — APPEND-ONLY HISTORY
--    Multiple rows per rule are expected:
--      • 'initial'         when the rule is first extracted
--      • 'prompt_revised'  when judge prompt is bumped (batch rerun)
--      • 'human_disagreed' when a human label flagged the previous decision
--      • 'manual_rerun'    operator action
-- -----------------------------------------------------------------------------

CREATE TABLE rule_llm_decision (
    id                    UUID PRIMARY KEY DEFAULT uuid(),
    rule_id               UUID NOT NULL REFERENCES rule(id),
    judge_model           TEXT NOT NULL,             -- 'anthropic/claude-haiku-4-5'
    judge_prompt_version  TEXT NOT NULL,             -- 'v3.2-2026-05'
    triggered_by          judge_decision_trigger NOT NULL,
    -- Full exchange so labelers (and prompt-tuning) see exactly what the judge
    -- was asked and what it actually said, including parse failures.
    prompt_messages       JSON NOT NULL,             -- [{role, content}, ...]
    raw_response          TEXT NOT NULL,             -- model's text, pre-parse
    parse_ok              BOOLEAN NOT NULL,
    parse_error           TEXT,                      -- non-null iff parse_ok = false
    -- Parsed classification (NULL when parse_ok = false)
    specificity           rule_specificity,
    cognitive_load        rule_cognitive_load,
    constraint_level      rule_constraint_level,
    enforcement_mechanism enforcement_mechanism,
    enforcement_scope     enforcement_scope,
    enforcement_trigger   enforcement_trigger,
    rule_kind             rule_kind,
    artifacts_required    artifact_required[] NOT NULL DEFAULT [],
    confidence            REAL CHECK (confidence BETWEEN 0 AND 1),
    rationale             TEXT,
    -- Ops metadata
    latency_ms            INTEGER,
    input_tokens          INTEGER,
    output_tokens         INTEGER,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX rule_llm_decision_rule_idx   ON rule_llm_decision (rule_id, created_at DESC);
CREATE INDEX rule_llm_decision_prompt_idx ON rule_llm_decision (judge_prompt_version);

-- -----------------------------------------------------------------------------
-- 5. Human labels — APPEND-ONLY, ANCHORED TO A SPECIFIC LLM DECISION
--    Every human label is a response to a specific decision the labeler was
--    looking at when they hit the keyboard shortcut. Disposition tells the
--    classification view how to treat it:
--      confirmed_llm    → use the LLM decision verbatim
--      revised_llm      → use the human-provided field values
--      rejected         → exclude rule from "Classified Rules"
--      marked_duplicate → rule rolls up into merged_into_rule_id's cluster
-- -----------------------------------------------------------------------------

CREATE TABLE rule_human_label (
    id                       UUID PRIMARY KEY DEFAULT uuid(),
    rule_id                  UUID NOT NULL REFERENCES rule(id),
    reviewed_llm_decision_id UUID NOT NULL REFERENCES rule_llm_decision(id),
    labeler_handle           TEXT NOT NULL,            -- 'alice@example.com'
    disposition              human_label_disposition NOT NULL,
    -- Populated for disposition='revised_llm'; NULL otherwise.
    specificity              rule_specificity,
    cognitive_load           rule_cognitive_load,
    constraint_level         rule_constraint_level,
    enforcement_mechanism    enforcement_mechanism,
    enforcement_scope        enforcement_scope,
    enforcement_trigger      enforcement_trigger,
    rule_kind                rule_kind,
    artifacts_required       artifact_required[] NOT NULL DEFAULT [],
    -- For 'marked_duplicate': the canonical rule this one folds into.
    merged_into_rule_id      UUID REFERENCES rule(id),
    -- Free-text feedback. Channel for the "Revise eval" arrow — prompt-revision
    -- tooling consumes these notes when bumping judge_prompt_version.
    note                     TEXT,
    submitted_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((disposition = 'marked_duplicate') = (merged_into_rule_id IS NOT NULL))
);
CREATE INDEX rule_human_label_rule_idx     ON rule_human_label (rule_id, submitted_at DESC);
CREATE INDEX rule_human_label_reviewed_idx ON rule_human_label (reviewed_llm_decision_id);

-- -----------------------------------------------------------------------------
-- 6. Semantic duplicate handling — "duplicate rules by meaning"
--    A cluster = a set of rules that mean the same thing. canonical_rule_id is
--    the representative shown in the feed / counted as unique.
-- -----------------------------------------------------------------------------

CREATE TABLE rule_semantic_cluster (
    id                  UUID PRIMARY KEY DEFAULT uuid(),
    canonical_rule_id   UUID NOT NULL REFERENCES rule(id) UNIQUE,
    meaning_signature   TEXT,                          -- LLM-paraphrased intent (~1 line)
    member_count        INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rule_semantic_cluster_member (
    cluster_id          UUID NOT NULL REFERENCES rule_semantic_cluster(id),
    rule_id             UUID NOT NULL REFERENCES rule(id) UNIQUE,  -- in at most one cluster
    similarity_score    REAL,                                       -- cosine to canonical
    method              semantic_cluster_method NOT NULL,
    -- Pointer to the evidence that put this rule in the cluster:
    --   embedding_threshold → NULL
    --   llm_pair_judge      → a rule_llm_decision.id from a pair-judge call
    --   human_merge         → a rule_human_label.id with disposition='marked_duplicate'
    method_evidence_id  UUID,
    added_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cluster_id, rule_id)
);
CREATE INDEX rule_semantic_member_cluster_idx ON rule_semantic_cluster_member (cluster_id);

-- -----------------------------------------------------------------------------
-- 7. "Classified Rules" view — human override > most recent successful LLM
-- -----------------------------------------------------------------------------

CREATE VIEW rule_classification_current AS
WITH human_latest AS (
    SELECT rule_id,
           ROW_NUMBER() OVER (PARTITION BY rule_id ORDER BY submitted_at DESC) AS rn,
           id AS source_id, submitted_at AS decided_at,
           specificity, cognitive_load, constraint_level,
           enforcement_mechanism, enforcement_scope, enforcement_trigger,
           rule_kind, artifacts_required
    FROM rule_human_label
    WHERE disposition IN ('confirmed_llm','revised_llm')
),
llm_latest AS (
    SELECT rule_id,
           ROW_NUMBER() OVER (PARTITION BY rule_id ORDER BY created_at DESC) AS rn,
           id AS source_id, created_at AS decided_at,
           specificity, cognitive_load, constraint_level,
           enforcement_mechanism, enforcement_scope, enforcement_trigger,
           rule_kind, artifacts_required
    FROM rule_llm_decision
    WHERE parse_ok = TRUE
)
SELECT r.id AS rule_id,
       CASE WHEN h.rule_id IS NOT NULL THEN 'human' ELSE 'llm' END AS decision_source,
       COALESCE(h.source_id, l.source_id) AS decision_id,
       COALESCE(h.specificity,           l.specificity)           AS specificity,
       COALESCE(h.cognitive_load,        l.cognitive_load)        AS cognitive_load,
       COALESCE(h.constraint_level,      l.constraint_level)      AS constraint_level,
       COALESCE(h.enforcement_mechanism, l.enforcement_mechanism) AS enforcement_mechanism,
       COALESCE(h.enforcement_scope,     l.enforcement_scope)     AS enforcement_scope,
       COALESCE(h.enforcement_trigger,   l.enforcement_trigger)   AS enforcement_trigger,
       COALESCE(h.rule_kind,             l.rule_kind)             AS rule_kind,
       COALESCE(h.artifacts_required,    l.artifacts_required)    AS artifacts_required,
       COALESCE(h.decided_at,            l.decided_at)            AS decided_at
FROM rule r
LEFT JOIN human_latest h ON h.rule_id = r.id AND h.rn = 1
LEFT JOIN llm_latest   l ON l.rule_id = r.id AND l.rn = 1;

-- Feed for the labeling UI: rules whose current classification is still LLM-only.
CREATE VIEW rule_pending_review AS
SELECT c.rule_id, c.decided_at
FROM rule_classification_current c
LEFT JOIN rule_human_label h ON h.rule_id = c.rule_id
WHERE c.decision_source = 'llm'
  AND h.id IS NULL;

-- -----------------------------------------------------------------------------
-- 8. Ops / observability
-- -----------------------------------------------------------------------------

CREATE TABLE ingestion_run (
    id              UUID PRIMARY KEY DEFAULT uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          ingestion_status NOT NULL DEFAULT 'running',
    source_query    TEXT NOT NULL,
    projects_seen   INTEGER NOT NULL DEFAULT 0,
    files_fetched   INTEGER NOT NULL DEFAULT 0,
    rules_extracted INTEGER NOT NULL DEFAULT 0,
    rules_new       INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    crawler_version TEXT NOT NULL
);

CREATE TABLE ingestion_event (
    id              BIGINT PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES ingestion_run(id),
    event_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    level           TEXT NOT NULL CHECK (level IN ('debug','info','warn','error')),
    message         TEXT NOT NULL,
    payload         JSON
);
CREATE SEQUENCE ingestion_event_id_seq START 1;

CREATE TABLE crawl_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
