#!/usr/bin/env python3
"""Split JSONL records and delegate validation to the canonical check-jsonschema CLI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--schemafile',required=True)
parser.add_argument('files',nargs='+')
args=parser.parse_args()
status=0
with tempfile.TemporaryDirectory(prefix='jsonl-records-') as directory:
    for filename in args.files:
        count=0
        with open(filename,encoding='utf-8') as stream:
            for line_no,line in enumerate(stream,1):
                if not line.strip(): continue
                count+=1
                try: value=json.loads(line)
                except ValueError as exc:
                    print(f'{filename}:{line_no}: invalid JSON: {exc}',file=sys.stderr);status=1;continue
                path=Path(directory)/'record.json';path.write_text(json.dumps(value))
                result=subprocess.run(['check-jsonschema','--schemafile',str(Path(args.schemafile).resolve()),str(path)],capture_output=True,text=True)
                if result.returncode:
                    print(f'{filename}:{line_no}: {result.stdout}{result.stderr}',file=sys.stderr)
                    status=max(status,result.returncode)
        if not count: print(f'{filename}: no JSONL records',file=sys.stderr);status=max(status,2)
sys.exit(status)
