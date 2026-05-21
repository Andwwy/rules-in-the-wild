import type {
  ClassificationItem,
  ClassificationLabel,
  Decision,
  ExtractionItem,
  ExtractionLabel,
  StatusFilter,
} from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function getExtractionItems(status: StatusFilter): Promise<ExtractionItem[]> {
  return request(`/api/extraction-items?status=${status}`);
}

export function saveExtractionLabel(
  targetKey: string,
  payload: {
    decision: Decision;
    corrected_rule_text: string | null;
    corrected_start_line: number | null;
    corrected_end_line: number | null;
    notes: string;
  },
): Promise<ExtractionLabel> {
  return request(`/api/extraction-labels/${targetKey}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function addMissingRule(payload: {
  document_id: string;
  source_path: string;
  rule_text: string;
  start_line: number;
  end_line: number;
  notes: string;
}): Promise<ExtractionLabel> {
  return request('/api/extraction-labels/missing', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getClassificationItems(status: StatusFilter): Promise<ClassificationItem[]> {
  return request(`/api/classification-items?status=${status}`);
}

export function saveClassificationLabel(
  targetKey: string,
  payload: {
    decision: Decision;
    corrected_prerequisites: string[];
    corrected_enforcement_mechanisms: string[];
    corrected_triggers: string[];
    corrected_ambiguity_level: string | null;
    corrected_ambiguity_notes: string;
    notes: string;
  },
): Promise<ClassificationLabel> {
  return request(`/api/classification-labels/${targetKey}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
