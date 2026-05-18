PIPELINE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS source_documents (
    document_id VARCHAR PRIMARY KEY,
    source_path VARCHAR NOT NULL,
    document_name VARCHAR NOT NULL,
    document_text VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    ingested_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    document_id VARCHAR PRIMARY KEY,
    model_alias VARCHAR NOT NULL,
    raw_response JSON NOT NULL,
    extracted_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS extracted_rules (
    rule_id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    rule_index INTEGER NOT NULL,
    rule_text VARCHAR NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    extracted_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS classification_runs (
    rule_id VARCHAR PRIMARY KEY,
    model_alias VARCHAR NOT NULL,
    raw_response JSON NOT NULL,
    classified_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS classified_rules (
    rule_id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    rule_text VARCHAR NOT NULL,
    prerequisites JSON NOT NULL,
    enforcement_mechanisms JSON NOT NULL,
    triggers JSON NOT NULL,
    ambiguity_level VARCHAR NOT NULL,
    ambiguity_notes VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    classified_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);
"""
