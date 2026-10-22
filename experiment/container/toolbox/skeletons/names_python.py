# Names in Python code, with Python's own parser. `text`: the file's text.
import ast
for n in ast.walk(ast.parse(text)):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        print(type(n).__name__, n.name, n.lineno, n.end_lineno)      # kind, name, first and last line
