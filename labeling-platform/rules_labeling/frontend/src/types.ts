export type Decision = 'accept' | 'correct' | 'reject' | 'skip';
export type AmbiguityLevel = 'none' | 'low' | 'medium' | 'high';
export type StatusFilter = 'all' | 'unlabeled' | 'labeled';

export interface SourceLine {
  line_number: number;
  text: string;
}

export interface ExtractionLabel {
  target_key: string;
  decision: Decision;
  corrected_rule_text: string | null;
  corrected_start_line: number | null;
  corrected_end_line: number | null;
  notes: string;
  is_missing: boolean;
}

export interface ExtractionItem {
  target_key: string;
  document_id: string;
  source_path: string;
  rule_id: string | null;
  rule_text: string;
  start_line: number;
  end_line: number;
  source_lines: SourceLine[];
  label: ExtractionLabel | null;
}

export interface ClassificationPrediction {
  prerequisites: string[];
  enforcement_mechanisms: string[];
  triggers: string[];
  ambiguity_level: string;
  ambiguity_notes: string;
  confidence: number;
}

export interface ClassificationLabel {
  target_key: string;
  decision: Decision;
  corrected_prerequisites: string[];
  corrected_enforcement_mechanisms: string[];
  corrected_triggers: string[];
  corrected_ambiguity_level: AmbiguityLevel | null;
  corrected_ambiguity_notes: string;
  notes: string;
}

export interface ClassificationItem {
  target_key: string;
  document_id: string;
  source_path: string;
  rule_id: string | null;
  rule_text: string;
  start_line: number;
  end_line: number;
  source_lines: SourceLine[];
  prediction: ClassificationPrediction | null;
  label: ClassificationLabel | null;
}

export interface Stats {
  documents: number;
  extraction_items: number;
  extraction_labels: number;
  classification_items: number;
  classification_labels: number;
}
