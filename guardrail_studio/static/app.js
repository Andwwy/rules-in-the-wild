const $ = id => document.getElementById(id);
const pretty = value => JSON.stringify(value, null, 2);
let config, selected = null, example = null, generated = null, busy = false;

function notice(message) {
  $('notice').hidden = !message;
  $('notice').textContent = message || '';
}
function setBusy(value, action) {
  busy = value;
  for (const id of ['route', 'test', 'download']) $(id).disabled = value;
  $('generate').disabled = value || !selected;
  const generating = value && action === 'Generating…';
  $('generate').setAttribute('aria-busy', String(generating));
  $('generate-spinner').hidden = !generating;
  $('generate-label').textContent = generating ? 'Generating…' : 'Generate';
  document.querySelectorAll('.route-card,.examples button').forEach(x => x.disabled = value);
  for (const id of ['rule', 'context', 'spec', 'file-scope', 'danger-mode', 'danger-base', 'input-mode']) $(id).disabled = value;
  if (!value && generated?.spec.generator === 'danger') updateDangerMode();
  if (action) $('route-source').textContent = action;
}
async function api(path, body, blob = false) {
  const response = await fetch('/api/' + path, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Studio-Token': config.token}, body: JSON.stringify(body)
  });
  if (!response.ok) { const error = await response.json(); throw Error(error.error || 'Request failed'); }
  return blob ? response.blob() : response.json();
}
function renderRoutes() {
  $('diff-defaults').hidden = selected !== 'danger';
  $('routes').replaceChildren();
  for (const [id, item] of Object.entries(config.catalog)) {
    const row = document.createElement('div');
    row.className = 'route-option' + (selected === id ? ' selected' : '');
    const heading = document.createElement('div'); heading.className = 'route-heading';
    const button = document.createElement('button');
    button.className = 'route-card';
    button.type = 'button'; button.setAttribute('aria-pressed', selected === id);
    const radio = document.createElement('span'); radio.className = 'route-radio'; radio.setAttribute('aria-hidden', 'true');
    const title = document.createElement('span'); title.textContent = item.category;
    button.append(radio, title); button.disabled = busy;
    const link = document.createElement('a');
    link.className = 'enforcer-link'; link.textContent = item.enforcer;
    link.href = item.docs_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', item.enforcer + ' documentation (opens in a new tab)');
    const sub = document.createElement('p'); sub.className = 'route-summary'; sub.textContent = item.summary;
    sub.id = 'route-summary-' + id; button.setAttribute('aria-describedby', sub.id);
    heading.append(button, link); row.append(heading, sub);
    row.onclick = event => {
      if (event.target.closest('a') || busy) return;
      selected = id; if (example?.spec.generator !== id) example = null;
      $('route-source').textContent = 'Manual';
      $('route-detail').textContent = 'Selected by you. Generate will translate to this checker’s native format.';
      resetOutput(); renderRoutes();
      $('routes').querySelector('[aria-pressed="true"]').focus();
    };
    $('routes').append(row);
  }
  $('generate').disabled = busy || !selected;
}
function resetOutput() {
  generated = null; $('generated').hidden = true; $('empty-output').hidden = false; $('output-state').textContent = '';
}
function inputChanged() {
  example = null; selected = null; resetOutput(); renderRoutes();
  $('route-source').textContent = 'Rule changed';
  $('route-detail').textContent = 'Route the updated rule to get a fresh recommendation.'; notice('');
}
$('rule').oninput = inputChanged; $('context').oninput = inputChanged;
$('route').onclick = async () => {
  if (!$('rule').value.trim()) { notice('Enter a rule first.'); $('rule').focus(); return; }
  notice(''); setBusy(true, 'Routing…');
  try {
    const result = await api('route', {rule: $('rule').value, context: $('context').value});
    selected = config.catalog[result.generator] ? result.generator : null; example = null; resetOutput();
    $('route-source').textContent = 'Jev';
    $('route-detail').textContent = selected
      ? `${config.catalog[selected].label} · model confidence ${result.confidence == null ? 'unavailable' : Math.round(result.confidence * 100) + '%'}. Confidence is not a correctness guarantee.`
      : ({needs_context: 'Add the missing language, contract, or semantic definitions. Deployment paths alone do not block a reusable checker.',
          deferred: 'This needs runtime or workflow enforcement outside these artifact checkers.',
          unsupported: 'The available targets cannot faithfully cover the entire rule.'}[result.generator] || result.generator);
    renderRoutes();
  } catch (error) { notice(error.message); $('route-source').textContent = 'Routing failed'; }
  finally { setBusy(false); }
};
function updateDangerMode() {
  const branch = $('danger-mode').value === 'branch'; $('danger-base').disabled = busy || !branch;
  $('danger-mode-note').textContent = branch
    ? 'Committed HEAD compared with the merge base of this ref. Staged and unstaged changes are excluded.'
    : 'The staged index compared with HEAD. Unstaged and untracked files are excluded.';
}
$('danger-mode').onchange = updateDangerMode;
async function readSpec() {
  const spec = structuredClone(generated.spec);
  if (spec.generator === 'danger') {
    spec.config.mode = $('danger-mode').value;
    spec.config.base = spec.config.mode === 'staged' ? 'HEAD' : $('danger-base').value.trim();
  }
  if (spec.generator === 'json_schema') {
    const globs = $('file-scope').value.split(',').map(x => x.trim()).filter(Boolean);
    spec.scope = globs.length ? {include: globs, exclude: spec.scope?.exclude || []} : null;
  }
  return (await api('source', {spec, content: $('spec').value})).spec;
}
function inputModes(kind) {
  if (kind === 'json_schema') return [['document', 'JSON document'], ['files', 'JSON / YAML / JSONL file fixtures']];
  if (kind === 'regex') return [['text', 'Plain text'], ['files', 'Text file fixtures']];
  return [[kind === 'conftest' ? 'manifest' : kind === 'danger' ? 'git' : 'files',
    kind === 'conftest' ? 'Path inventory' : kind === 'danger' ? 'Git diff fixture' : 'Source file fixtures']];
}
function showArtifact(value) {
  const kind = generated.spec.generator;
  let content = value;
  if (kind === 'json_schema' && Object.hasOwn(value, 'document')) { $('input-mode').value = 'document'; content = value.document; }
  else if (kind === 'regex' && Object.hasOwn(value, 'text')) { $('input-mode').value = 'text'; content = value.text; }
  else if (value.files) $('input-mode').value = 'files';
  $('artifact').value = $('input-mode').value === 'text' ? content : pretty(content);
}
function showGenerated(result) {
  generated = result; $('generated').hidden = false; $('empty-output').hidden = true;
  $('output-state').textContent = result.source === 'example' ? 'Example' : 'Generated · review needed';
  $('explanation').textContent = result.explanation;
  const kind = result.spec.generator;
  $('spec').value = result.artifact.content;
  $('code-label').textContent = result.artifact.filename;
  $('spec').setAttribute('aria-label', 'Editable ' + result.artifact.filename);
  $('execution-hint').textContent = result.artifact.command;
  $('schema-binding').hidden = kind !== 'json_schema';
  $('file-scope').value = result.spec.scope?.include?.join(', ') || '';
  $('danger-binding').hidden = kind !== 'danger';
  if (kind === 'danger') {
    $('danger-mode').value = result.spec.config.mode;
    $('danger-base').value = result.spec.config.mode === 'branch' ? result.spec.config.base : 'main'; updateDangerMode();
  }
  $('input-mode').replaceChildren();
  for (const [value, label] of inputModes(kind)) { const option = document.createElement('option'); option.value = value; option.textContent = label; $('input-mode').append(option); }
  $('test-hint').textContent = kind === 'danger' ? 'Offline fixture test. The downloaded Dangerfile runs locally in Git.' : 'Runs the native checker against this input.';
  showArtifact(result.pass);
  const definition = result.native_validation;
  $('test-result').textContent = definition ? pretty(definition) : 'No test run yet.';
  $('test-result').className = definition?.status === 'error' ? 'error' : '';
  if (definition?.status === 'error') $('output-state').textContent = 'Native validation failed · edit the source';
  $('output').scrollIntoView({behavior: 'smooth', block: 'start'});
}
$('generate').onclick = async () => {
  notice(''); setBusy(true, 'Generating…');
  try {
    if (example && selected === example.spec.generator) {
      showGenerated({...structuredClone(example), source: 'example', explanation: 'Hand-authored example. Edit the rule to use live generation.'});
    } else {
      const result = await api('generate', {rule: $('rule').value, context: $('context').value, generator: selected});
      if (result.status !== 'generated') { notice(result.explanation); resetOutput(); }
      else showGenerated(result);
    }
  } catch (error) { notice(error.message); }
  finally { setBusy(false); $('route-source').textContent = example ? 'Example' : 'Selected'; }
};
$('pass-example').onclick = () => { if (generated) showArtifact(generated.pass); };
$('fail-example').onclick = () => { if (generated) showArtifact(generated.fail); };
$('test').onclick = async () => {
  notice(''); setBusy(true); $('test-result').textContent = 'Running check…';
  try {
    const spec = await readSpec();
    const mode = $('input-mode').value;
    const value = mode === 'text' ? $('artifact').value : JSON.parse($('artifact').value);
    const artifact = mode === 'text' ? {text: value} : mode === 'document' ? {document: value} : value;
    const result = await api('test', {spec, artifact});
    $('test-result').className = result.status; $('test-result').textContent = pretty(result);
  } catch (error) { $('test-result').className = 'error'; $('test-result').textContent = error.message; }
  finally { setBusy(false); }
};
$('copy').onclick = async () => {
  try { await navigator.clipboard.writeText($('spec').value); $('copy').textContent = 'Copied'; setTimeout(() => $('copy').textContent = 'Copy', 1500); }
  catch (_) { notice('Select the source and copy it manually.'); }
};
$('download').onclick = async () => {
  notice(''); setBusy(true);
  try {
    const blob = await api('bundle', {spec: await readSpec()}, true);
    const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'guardrail.zip'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { notice(error.message); }
  finally { setBusy(false); }
};
(async () => {
  try {
    config = await (await fetch('/api/config')).json();
    $('connection').textContent = config.jev_ready ? 'Jev configured' : 'Jev key needed';
    $('generation-note').textContent = 'Generate uses your local Codex CLI.'; renderRoutes();
    for (const item of config.examples) {
      const button = document.createElement('button'); button.textContent = item.label;
      button.onclick = () => {
        example = item; selected = item.spec.generator; $('rule').value = item.rule; $('context').value = item.context;
        $('route-source').textContent = 'Example'; $('route-detail').textContent = 'Preselected example. Find generator asks Jev instead.';
        resetOutput(); notice(''); renderRoutes();
      };
      $('examples').append(button);
    }
  } catch (_) { notice('Could not connect to the local server.'); }
})();
