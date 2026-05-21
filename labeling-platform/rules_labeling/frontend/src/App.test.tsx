import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

const extractionItem = {
  target_key: 'target-1',
  document_id: 'doc-1',
  source_path: '/tmp/AGENTS.md',
  rule_id: 'rule-1',
  rule_text: 'The agent must inspect files.',
  start_line: 2,
  end_line: 2,
  source_lines: [
    { line_number: 1, text: 'Intro' },
    { line_number: 2, text: 'The agent must inspect files.' },
  ],
  label: null,
};

const classificationItem = {
  ...extractionItem,
  prediction: {
    prerequisites: ['before editing'],
    enforcement_mechanisms: ['review'],
    triggers: ['code change'],
    ambiguity_level: 'low',
    ambiguity_notes: 'clear',
    confidence: 0.9,
  },
};

describe('rules labeling', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.startsWith('/api/extraction-items')) {
          return jsonResponse([extractionItem]);
        }
        if (url.startsWith('/api/classification-items')) {
          return jsonResponse([classificationItem]);
        }
        if (url.startsWith('/api/extraction-labels') && init?.method === 'PUT') {
          return jsonResponse({ target_key: 'target-1', decision: 'correct' });
        }
        if (url.startsWith('/api/classification-labels') && init?.method === 'PUT') {
          return jsonResponse({ target_key: 'target-1', decision: 'correct' });
        }
        if (url === '/api/extraction-labels/missing') {
          return jsonResponse({ target_key: 'target-2', decision: 'correct' });
        }
        return jsonResponse({});
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('loads extraction items and saves a correction', async () => {
    render(<App />);

    expect(await screen.findByDisplayValue('The agent must inspect files.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Correct' }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/extraction-labels/target-1',
        expect.objectContaining({ method: 'PUT' }),
      );
    });
  });

  it('loads classification items and saves edited fields', async () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /classification/i }));
    expect(await screen.findByDisplayValue('before editing')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Correct' }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/classification-labels/target-1',
        expect.objectContaining({ method: 'PUT' }),
      );
    });
  });
});

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
