# A filter: replaces what the rule forbids, so the result follows it. `text`: the target's text.
import re
PATTERN, REPLACEMENT = re.compile(r"<pattern>"), r"<replacement>"
fixed = PATTERN.sub(REPLACEMENT, text)                # write `fixed` back; tell the agent what changed
