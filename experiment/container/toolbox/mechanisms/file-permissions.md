# File permissions
mechanism · before, at every moment

Root owns the file and its folder; the agent can read but not write it (`chown root:root <file> <folder>`;
`chmod 0644 <file>`, `chmod 0755 <folder>`), or not read it (`chmod 0600 <file>`).

- in /workspace: the folder is root's with the sticky bit (as /tmp): the agent can change, move or remove only its own files; a file that root owns there, it can do none of these to.
- immutable: `chattr +i <file>` (as root): no user can change, move or remove the file, whatever owns its folder; `chattr -i` undoes it.
- the agent sees: the system's error ("Permission denied", "Operation not permitted"), without the rule: put the reason where the agent reads it (a note in the folder, a comment in the file).
- limits: in a folder that the agent owns (one it made), it can move or remove root's file unless the file is immutable.

- docs: https://man7.org/linux/man-pages/man1/chmod.1.html
