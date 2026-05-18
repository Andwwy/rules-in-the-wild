-- Extract normative rules from each ingested document with Flock.
--
-- Inputs:
--   source_documents
-- Session variables set by run.py:
--   rules_model_alias VARCHAR
--   force_rerun BOOLEAN
--   rules_extract_prompt_name VARCHAR

CREATE OR REPLACE TEMP TABLE extraction_candidates AS
SELECT
    d.document_id,
    d.source_path,
    d.document_name,
    d.document_text,
    string_agg(
        line_number.i::VARCHAR || chr(9) || list_extract(document_lines.lines, line_number.i),
        chr(10)
        ORDER BY line_number.i
    ) AS line_numbered_document_text
FROM source_documents d
CROSS JOIN LATERAL (
    SELECT string_split(replace(d.document_text, chr(13), ''), chr(10)) AS lines
) AS document_lines
CROSS JOIN range(1, length(document_lines.lines) + 1) AS line_number(i)
LEFT JOIN extraction_runs r USING (document_id)
WHERE getvariable('force_rerun')::BOOLEAN OR r.document_id IS NULL
GROUP BY d.document_id, d.source_path, d.document_name, d.document_text, r.document_id;

INSERT OR REPLACE INTO extraction_runs (document_id, model_alias, raw_response, extracted_at)
WITH responses AS (
    SELECT
        document_id,
        to_json(llm_complete(
            {
                'model_name': getvariable('rules_model_alias')::VARCHAR
            },
            {
                'prompt_name': getvariable('rules_extract_prompt_name')::VARCHAR,
                'context_columns': [
                    {
                        'data': concat(
                            'Document name: ', document_name,
                            chr(10),
                            'Source path: ', source_path,
                            chr(10), chr(10),
                            'Line-numbered document text. Each line is: line_number, tab, text.',
                            chr(10),
                            line_numbered_document_text
                        )
                    }
                ]
            }
        )::VARCHAR) AS raw_response
    FROM extraction_candidates
)
SELECT
    document_id,
    getvariable('rules_model_alias')::VARCHAR AS model_alias,
    raw_response,
    current_timestamp AS extracted_at
FROM responses;

DELETE FROM extracted_rules
WHERE document_id IN (SELECT document_id FROM extraction_candidates);

INSERT INTO extracted_rules (
    rule_id,
    document_id,
    source_path,
    rule_index,
    rule_text,
    start_line,
    end_line,
    extracted_at
)
WITH expanded AS (
    SELECT
        r.document_id,
        d.source_path,
        idx.i - 1 AS rule_index,
        list_extract(fields.parts, 1) AS rule_text,
        coalesce(try_cast(list_extract(fields.parts, 2) AS INTEGER), 0) AS start_line,
        coalesce(try_cast(list_extract(fields.parts, 3) AS INTEGER), 0) AS end_line,
        r.extracted_at
    FROM extraction_runs r
    JOIN source_documents d USING (document_id)
    JOIN extraction_candidates c USING (document_id)
    CROSS JOIN LATERAL (
        SELECT string_split(replace(coalesce(json_extract_string(r.raw_response, '$'), ''), chr(13), ''), chr(10)) AS lines
    ) AS output
    CROSS JOIN range(1, length(output.lines) + 1) AS idx(i)
    CROSS JOIN LATERAL (
        SELECT string_split(list_extract(output.lines, idx.i), chr(9)) AS parts
    ) AS fields
    WHERE length(trim(coalesce(list_extract(output.lines, idx.i), ''))) > 0
),
typed AS (
    SELECT
        sha256(document_id || ':' || rule_index::VARCHAR || ':' || rule_text) AS rule_id,
        document_id,
        source_path,
        rule_index,
        rule_text,
        start_line,
        greatest(start_line, end_line) AS end_line,
        extracted_at
    FROM expanded
)
SELECT *
FROM typed
WHERE rule_text IS NOT NULL AND length(trim(rule_text)) > 0;
