# The rule's part of check.py for a JSON Schema (enforce install jsonschema;
# run with /opt/enforce/tool-installs/jsonschema/bin/python).
import json
import jsonschema

SCHEMA = json.load(open("<schema.json>", encoding="utf-8"))

def problems(text, where):
    return [f"{where}: {'/'.join(map(str, e.path)) or '/'} {e.message}"
            for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(json.loads(text))]
