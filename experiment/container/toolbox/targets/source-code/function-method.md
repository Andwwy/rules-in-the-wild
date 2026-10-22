# Source code › Function / method
target · A function or a method.

- where: in the source files; read them with a parser (/opt/enforce-toolbox/skeletons/names_python.py, /opt/enforce-toolbox/skeletons/names_js.py), or with Semgrep patterns
- which files: every file that holds code, decided when the check runs (/opt/enforce-toolbox/targets/source-code/source-file.md); take embedded code out of its container first (a `<script>` in HTML), then parse it
