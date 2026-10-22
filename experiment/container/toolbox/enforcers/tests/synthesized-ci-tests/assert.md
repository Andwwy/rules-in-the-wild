# Tests › Synthesized CI tests › ASSERT
enforcer · Turns a written behavior (a policy) into a rubric, generates single-turn and multi-turn test cases, runs them against
the AI system (a model, an app or an agent) and has an LLM judge score each transcript against the rubric. The judge is
a model: its verdicts are not deterministic.

- no recipe: Python venv with assert-ai; needs a model API key
- check: `assert-ai run --config eval_config.yaml`; the judge's verdict on each transcript

From the leaf's note:

Install: `python3 -m venv /opt/enforce/assert-venv && /opt/enforce/assert-venv/bin/pip install assert-ai==0.3.0`; it
calls models through LiteLLM, so it needs a model API key.
Use: `assert-ai run --config eval_config.yaml` (the behavior, the context, the test set, the target, the judge); the
target is a Python callable or an agent traced through OpenInference.

Docs: https://github.com/responsibleai/ASSERT
