# A check over the whole project; print `out` and exit 1 if it is not empty (as check.py).
import os
SKIP = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
out = []
for d, dirs, files in os.walk("/workspace"):
    dirs[:] = [x for x in dirs if x not in SKIP]
    for f in files:
        path = os.path.join(d, f)
        # <the property>: out.append(f"{path}: <what breaks the rule>; <what to change>")
        pass
