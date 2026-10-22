# The rule's part of check.py (/opt/enforce-toolbox/skeletons/check.py): a regular expression on each line.
import re
PATTERN = re.compile(r"<pattern>")                    # here: the text must not match; for "must match", invert it

def problems(text, where):
    return [f"{where}:{n}: '{m.group(0)}' breaks the rule; <what to change>"
            for n, line in enumerate(text.splitlines(), 1) if (m := PATTERN.search(line))]
