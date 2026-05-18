import type { Decision, SourceLine, StatusFilter } from './types';

export function StatusSelect({
  value,
  onChange,
}: {
  value: StatusFilter;
  onChange: (value: StatusFilter) => void;
}) {
  return (
    <label className="field compact">
      Status
      <select value={value} onChange={(event) => onChange(event.target.value as StatusFilter)}>
        <option value="unlabeled">Unlabeled</option>
        <option value="all">All</option>
        <option value="labeled">Labeled</option>
      </select>
    </label>
  );
}

export function DecisionButtons({
  onSave,
}: {
  onSave: (decision: Decision) => void;
}) {
  return (
    <div className="button-row">
      <button onClick={() => onSave('accept')}>Accept</button>
      <button onClick={() => onSave('correct')}>Correct</button>
      <button onClick={() => onSave('reject')}>Reject</button>
      <button onClick={() => onSave('skip')}>Skip</button>
    </div>
  );
}

export function SourceLines({
  lines,
  startLine,
  endLine,
}: {
  lines: SourceLine[];
  startLine: number;
  endLine: number;
}) {
  return (
    <pre className="source-lines" aria-label="Source lines">
      {lines.map((line) => (
        <div
          key={line.line_number}
          className={line.line_number >= startLine && line.line_number <= endLine ? 'highlight' : ''}
        >
          <span>{line.line_number}</span>
          <code>{line.text || ' '}</code>
        </div>
      ))}
    </pre>
  );
}

export function parseList(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function formatList(value: string[]): string {
  return value.join('\n');
}
