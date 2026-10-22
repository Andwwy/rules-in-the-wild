# Commands › Text tools › grep
enforcer · Searches text with regular expressions (`-E` extended, `-P` Perl-style, `-n` line numbers, `-r` folders). It is in the
image. Exit code 0: a match was found.

- check: `grep -n -E '<pattern>' <file>`: exit 0 when it matches (a violation, for "must not"), 1 when it does not
