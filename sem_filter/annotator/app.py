"""Is-rule annotator.

Serves the clauses in 1000_sample.jsonl and writes the `human` field back to
that same file. Every label is persisted immediately (atomic rewrite), so the
file on disk is always the source of truth -- kill the container at any point
and nothing is lost.
"""
import json
import os
import tempfile
import threading

from flask import Flask, jsonify, request, send_from_directory

DATA = os.environ.get('DATA', '/data/1000_sample.jsonl')
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

app = Flask(__name__, static_folder=None)
_lock = threading.Lock()


def load():
    with open(DATA) as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    for r in rows:
        r.setdefault('reason', None)
    return rows


def save(rows):
    """Atomic rewrite: temp file in the same directory, then rename over."""
    d = os.path.dirname(os.path.abspath(DATA))
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.1000_sample.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        os.replace(tmp, DATA)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


ROWS = load()
INDEX = {r['clause_id']: i for i, r in enumerate(ROWS)}

# Optional sidecar mapping source_file sha -> {repo, path, link} (kept separate so
# provenance updates never touch, or race with, the annotation file itself).
_links_path = os.path.join(os.path.dirname(os.path.abspath(DATA)),
                           os.path.splitext(os.path.basename(DATA))[0] + '_links.json')
try:
    with open(_links_path) as fh:
        LINKS = json.load(fh)
except FileNotFoundError:
    LINKS = {}


def stats():
    done = sum(1 for r in ROWS if r['human'] is not None)
    agree = sum(1 for r in ROWS if r['human'] is not None and r['human'] == r['llm'])
    return {'total': len(ROWS), 'done': done, 'agree': agree,
            'yes': sum(1 for r in ROWS if r['human'] is True),
            'no': sum(1 for r in ROWS if r['human'] is False)}


@app.get('/')
def index():
    return send_from_directory(STATIC, 'index.html')


@app.get('/vendor/<path:name>')
def vendor(name):
    return send_from_directory(os.path.join(STATIC, 'vendor'), name)


@app.get('/api/clauses')
def clauses():
    return jsonify({'clauses': [
        {'i': i, 'clause_id': r['clause_id'], 'text': r['text'],
         'source_file': r['source_file'], 'llm': r['llm'], 'human': r['human'],
         'reason': r.get('reason'),
         'context': r.get('context'), 'ctx_start_line': r.get('ctx_start_line'),
         'heading_path': r.get('heading_path'),
         'origin': LINKS.get(r['source_file'])}
        for i, r in enumerate(ROWS)], 'stats': stats()})


@app.post('/api/label')
def label():
    """Partial update: any of `human` / `reason` present in the body is written."""
    body = request.get_json(force=True)
    cid = body.get('clause_id')
    if cid not in INDEX:
        return jsonify({'error': f'unknown clause_id {cid!r}'}), 404
    row = ROWS[INDEX[cid]]
    with _lock:
        if 'human' in body:
            if body['human'] not in (True, False, None):
                return jsonify({'error': 'human must be true, false or null'}), 400
            row['human'] = body['human']
        if 'reason' in body:
            reason = body['reason']
            if reason is not None and not isinstance(reason, str):
                return jsonify({'error': 'reason must be a string or null'}), 400
            row['reason'] = (reason or '').strip() or None
        save(ROWS)
    return jsonify({'ok': True, 'clause_id': cid, 'human': row['human'],
                    'reason': row['reason'], 'stats': stats()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
