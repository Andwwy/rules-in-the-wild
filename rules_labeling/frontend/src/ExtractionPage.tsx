import { Plus, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { addMissingRule, getExtractionItems, saveExtractionLabel } from './api';
import { DecisionButtons, SourceLines, StatusSelect } from './common';
import type { Decision, ExtractionItem, StatusFilter } from './types';

export function ExtractionPage() {
  const [status, setStatus] = useState<StatusFilter>('unlabeled');
  const [items, setItems] = useState<ExtractionItem[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>('');
  const [draft, setDraft] = useState({ ruleText: '', startLine: 1, endLine: 1, notes: '' });
  const [missing, setMissing] = useState({ documentId: '', sourcePath: '', ruleText: '', startLine: 1, endLine: 1, notes: '' });
  const [message, setMessage] = useState('');

  async function load() {
    const next = await getExtractionItems(status);
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
      ruleText: selected.label?.corrected_rule_text ?? selected.rule_text,
      startLine: selected.label?.corrected_start_line ?? selected.start_line,
      endLine: selected.label?.corrected_end_line ?? selected.end_line,
      notes: selected.label?.notes ?? '',
    });
    setMissing((current) => ({
      ...current,
      documentId: selected.document_id,
      sourcePath: selected.source_path,
      startLine: selected.start_line,
      endLine: selected.end_line,
    }));
  }, [selected?.target_key]);

  async function save(decision: Decision) {
    if (!selected) return;
    await saveExtractionLabel(selected.target_key, {
      decision,
      corrected_rule_text: decision === 'correct' ? draft.ruleText : null,
      corrected_start_line: decision === 'correct' ? draft.startLine : null,
      corrected_end_line: decision === 'correct' ? draft.endLine : null,
      notes: draft.notes,
    });
    setMessage(`Saved ${decision}`);
    await load();
  }

  async function saveMissing() {
    await addMissingRule({
      document_id: missing.documentId,
      source_path: missing.sourcePath,
      rule_text: missing.ruleText,
      start_line: missing.startLine,
      end_line: missing.endLine,
      notes: missing.notes,
    });
    setMessage('Added missing rule');
    setMissing((current) => ({ ...current, ruleText: '', notes: '' }));
    await load();
  }

  return (
    <main className="workbench">
      <aside className="queue">
        <div className="queue-header">
          <StatusSelect value={status} onChange={setStatus} />
          <button onClick={load} title="Refresh extraction queue">
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
          </div>
          <SourceLines lines={selected.source_lines} startLine={draft.startLine} endLine={draft.endLine} />
          <div className="editor-grid">
            <label className="field wide">
              Rule text
              <textarea value={draft.ruleText} onChange={(event) => setDraft({ ...draft, ruleText: event.target.value })} />
            </label>
            <label className="field">
              Start line
              <input type="number" value={draft.startLine} onChange={(event) => setDraft({ ...draft, startLine: Number(event.target.value) })} />
            </label>
            <label className="field">
              End line
              <input type="number" value={draft.endLine} onChange={(event) => setDraft({ ...draft, endLine: Number(event.target.value) })} />
            </label>
            <label className="field wide">
              Notes
              <input value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
            </label>
          </div>
          <DecisionButtons onSave={save} />

          <section className="missing-panel">
            <h2><Plus size={18} /> Add Missing Rule</h2>
            <div className="editor-grid">
              <label className="field wide">
                Rule text
                <textarea value={missing.ruleText} onChange={(event) => setMissing({ ...missing, ruleText: event.target.value })} />
              </label>
              <label className="field">
                Start line
                <input type="number" value={missing.startLine} onChange={(event) => setMissing({ ...missing, startLine: Number(event.target.value) })} />
              </label>
              <label className="field">
                End line
                <input type="number" value={missing.endLine} onChange={(event) => setMissing({ ...missing, endLine: Number(event.target.value) })} />
              </label>
              <label className="field wide">
                Notes
                <input value={missing.notes} onChange={(event) => setMissing({ ...missing, notes: event.target.value })} />
              </label>
            </div>
            <button onClick={saveMissing}>Add missing rule</button>
          </section>
          {message && <p className="message">{message}</p>}
        </section>
      ) : (
        <section className="empty">No extraction items found.</section>
      )}
    </main>
  );
}
