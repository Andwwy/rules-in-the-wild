# Validation › Regex › Regex filter
enforcer · A regular expression that finds text the rule forbids and replaces it, so the result follows the rule without a
second attempt.

- check: a regular expression that replaces what the rule forbids, so the result follows it; the mechanism must be able to write the target at that moment (or refuse the action and give the fixed text back)
- skeleton: /opt/enforce-toolbox/skeletons/regex_filter.py
