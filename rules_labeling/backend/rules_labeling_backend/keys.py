from __future__ import annotations

import hashlib
import re


def normalize_rule_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def extraction_target_key(
    *,
    document_id: str,
    start_line: int,
    end_line: int,
    rule_text: str,
) -> str:
    normalized = normalize_rule_text(rule_text)
    payload = f"{document_id}|{start_line}|{end_line}|{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
