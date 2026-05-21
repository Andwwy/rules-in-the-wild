import { RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getClassificationItems, saveClassificationLabel } from './api';
import { DecisionButtons, formatList, parseList, SourceLines, StatusSelect } from './common';
import type { ClassificationItem, Decision, StatusFilter } from './types';

export function ClassificationPage() {
  const [status, setStatus] = useState<StatusFilter>('unlabeled');
  const [items, setItems] = useState<ClassificationItem[]>([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [draft, setDraft] = useState({
    prerequisites: '',
    enforcement: '',
    triggers: '',
    ambiguityLevel: 'low',
    ambiguityNotes: '',
    notes: '',
  });
  const [message, setMessage] = useState('');

  async function load() {
    const next = await getClassificationItems(status);
    setItems(next);
    setSelectedKey((current) => current || next[0]?.target_key || '');
  }

  useEffect(() => {
    void load();
  }, [status]);

  const selected = useMemo(
    () => items.find((item) => item.target_key === selectedKey) ?? items[0],
    [items, selectedKey],
  );

  useEffect(() => {
    if (!selected) return;
    setDraft({
      prerequisites: formatList(selected.label?.corrected_prerequisites ?? selected.prediction?.prerequisites ?? []),
      enforcement: formatList(selected.label?.corrected_enforcement_mechanisms ?? selected.prediction?.enforcement_mechanisms ?? []),
      triggers: formatList(selected.label?.corrected_triggers ?? selected.prediction?.triggers ?? []),
      ambiguityLevel: selected.label?.corrected_ambiguity_level ?? selected.prediction?.ambiguity_level ?? 'low',
      ambiguityNotes: selected.label?.corrected_ambiguity_notes ?? selected.prediction?.ambiguity_notes ?? '',
      notes: selected.label?.notes ?? '',
    });
  }, [selected?.target_key]);

  async function save(decision: Decision) {
    if (!selected) return;
    await saveClassificationLabel(selected.target_key, {
      decision,
      corrected_prerequisites: parseList(draft.prerequisites),
      corrected_enforcement_mechanisms: parseList(draft.enforcement),
      corrected_triggers: parseList(draft.triggers),
      corrected_ambiguity_level: draft.ambiguityLevel,
      corrected_ambiguity_notes: draft.ambiguityNotes,
      notes: draft.notes,
    });
    setMessage(`Saved ${decision}`);
    await load();
  }

  return (
    <main className="workbench">
      <aside className="queue">
        <div className="queue-header">
          <StatusSelect value={status} onChange={setStatus} />
          <button onClick={load} title="Refresh classification queue">
            <RefreshCw size={16} />
          </button>
        </div>
        {items.map((item) => (
          <button
            key={item.target_key}
            className={item.target_key === selected?.target_key ? 'queue-item active' : 'queue-item'}
            onClick={() => setSelectedKey(item.target_key)}
          >
            <span>{item.rule_text}</span>
            <small>{item.label?.decision ?? 'unlabeled'}</small>
          </button>
        ))}
      </aside>

      {selected ? (
        <section className="detail">
          <div className="meta">
            <strong>{selected.source_path}</strong>
            <span>{selected.document_id}</span>
            <span>lines {selected.start_line}-{selected.end_line}</span>
          </div>
          <p className="rule-text">{selected.rule_text}</p>
          <SourceLines lines={selected.source_lines} startLine={selected.start_line} endLine={selected.end_line} />
          <div className="editor-grid">
            <label className="field">
              Prerequisites
              <textarea value={draft.prerequisites} onChange={(event) => setDraft({ ...draft, prerequisites: event.target.value })} />
            </label>
            <label className="field">
              Enforcement
              <textarea value={draft.enforcement} onChange={(event) => setDraft({ ...draft, enforcement: event.target.value })} />
            </label>
            <label className="field">
              Triggers
              <textarea value={draft.triggers} onChange={(event) => setDraft({ ...draft, triggers: event.target.value })} />
            </label>
            <label className="field">
              Ambiguity level
              <select value={draft.ambiguityLevel} onChange={(event) => setDraft({ ...draft, ambiguityLevel: event.target.value })}>
                <option value="none">none</option>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </label>
            <label className="field wide">
              Ambiguity notes
              <input value={draft.ambiguityNotes} onChange={(event) => setDraft({ ...draft, ambiguityNotes: event.target.value })} />
            </label>
            <label className="field wide">
              Label notes
              <input value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
            </label>
          </div>
          <DecisionButtons onSave={save} />
          {message && <p className="message">{message}</p>}
        </section>
      ) : (
        <section className="empty">No classification items found.</section>
      )}
    </main>
  );
}
