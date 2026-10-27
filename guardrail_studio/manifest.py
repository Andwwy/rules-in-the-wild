#!/usr/bin/env python3
"""Read-only repository inventory adapter. Contains no generated rule predicates."""
import argparse
import json
import os
from pathlib import Path


def collect(root):
    root = Path(root).resolve()
    if not root.is_dir(): raise ValueError('Inventory root must be a directory')
    entries = []
    def walk(directory):
        for entry in sorted(os.scandir(directory), key=lambda e:e.name):
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            if relative == '.git': continue
            if entry.is_symlink():
                entries.append({'path':relative,'kind':'symlink','target':os.readlink(path)})
            elif entry.is_dir(follow_symlinks=False):
                entries.append({'path':relative,'kind':'directory'})
                walk(path)
            elif entry.is_file(follow_symlinks=False):
                entries.append({'path':relative,'kind':'file'})
            else:
                entries.append({'path':relative,'kind':'other'})
    walk(root)
    return {'entries':entries}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',nargs='?',default='.')
    args=parser.parse_args()
    print(json.dumps(collect(args.root),indent=2))
