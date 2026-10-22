# Commands › Shell › CLI parser
enforcer · A check that parses a command line into its program, flags and arguments, for rules on which commands or flags may be
used.

- check: split the command line with Python's `shlex.split`, then check the program, its flags and arguments
