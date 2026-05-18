-- Classify extracted rules with Flock.
--
-- Inputs:
--   extracted_rules
-- Session variables set by run.py:
--   rules_model_alias VARCHAR
--   force_rerun BOOLEAN
--   rules_classify_prompt_name VARCHAR

CREATE OR REPLACE TEMP TABLE classification_candidates AS
SELECT
    r.rule_id,
    r.document_id,
    r.source_path,
    r.rule_text,
    r.start_line,
    r.end_line
FROM extracted_rules r
LEFT JOIN classification_runs c USING (rule_id)
WHERE getvariable('force_rerun')::BOOLEAN OR c.rule_id IS NULL;

INSERT OR REPLACE INTO classification_runs (rule_id, model_alias, raw_response, classified_at)
WITH responses AS (
    SELECT
        rule_id,
        to_json(llm_complete(
            {
                'model_name': getvariable('rules_model_alias')::VARCHAR
            },
            {
                'prompt_name': getvariable('rules_classify_prompt_name')::VARCHAR,
                'context_columns': [
                    {
                        'data': concat(
                            'Document ID: ', document_id,
                            chr(10),
                            'Source path: ', source_path,
                            chr(10),
                            'Start line: ', start_line::VARCHAR,
                            chr(10),
                            'End line: ', end_line::VARCHAR,
                            chr(10),
                            'Rule text: ', rule_text,
                            chr(10)
                        )
                    }
                ]
            }
        )::VARCHAR) AS raw_response
    FROM classification_candidates
)
SELECT
    rule_id,
    getvariable('rules_model_alias')::VARCHAR AS model_alias,
    raw_response,
    current_timestamp AS classified_at
FROM responses;

DELETE FROM classified_rules
WHERE rule_id IN (SELECT rule_id FROM classification_candidates);

INSERT INTO classified_rules (
    rule_id,
    document_id,
    source_path,
    rule_text,
    prerequisites,
    enforcement_mechanisms,
    triggers,
    ambiguity_level,
    ambiguity_notes,
    confidence,
    classified_at
)
SELECT
    r.rule_id,
    r.document_id,
    r.source_path,
    r.rule_text,
    CASE
        WHEN coalesce(list_extract(fields.parts, 1), '') = '' THEN '[]'::JSON
        ELSE to_json(string_split(list_extract(fields.parts, 1), '; '))
    END AS prerequisites,
    CASE
        WHEN coalesce(list_extract(fields.parts, 2), '') = '' THEN '[]'::JSON
        ELSE to_json(string_split(list_extract(fields.parts, 2), '; '))
    END AS enforcement_mechanisms,
    CASE
        WHEN coalesce(list_extract(fields.parts, 3), '') = '' THEN '[]'::JSON
        ELSE to_json(string_split(list_extract(fields.parts, 3), '; '))
    END AS triggers,
    coalesce(list_extract(fields.parts, 4), 'high') AS ambiguity_level,
    coalesce(list_extract(fields.parts, 5), '') AS ambiguity_notes,
    coalesce(try_cast(list_extract(fields.parts, 6) AS DOUBLE), 0.0) AS confidence,
    c.classified_at
FROM classification_runs c
JOIN extracted_rules r USING (rule_id)
JOIN classification_candidates cc USING (rule_id)
CROSS JOIN LATERAL (
    SELECT string_split(
        list_extract(
            string_split(replace(coalesce(json_extract_string(c.raw_response, '$'), ''), chr(13), ''), chr(10)),
            1
        ),
        chr(9)
    ) AS parts
) AS fields;
