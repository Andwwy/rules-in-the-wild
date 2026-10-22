# Names in JavaScript and TypeScript code, with tree-sitter (enforce install js-parser).
# Run with /opt/enforce/tool-installs/js-parser/bin/python. `text`: the file's text.
import tree_sitter_javascript, tree_sitter_typescript
from tree_sitter import Language, Parser
lang = Language(tree_sitter_javascript.language())          # .ts: tree_sitter_typescript.language_typescript()
tree = Parser(lang).parse(text.encode())
KINDS = {"function_declaration", "method_definition", "class_declaration",       # JavaScript and TypeScript
         "interface_declaration", "type_alias_declaration"}                       # TypeScript
def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)
for n in walk(tree.root_node):
    name = n.child_by_field_name("name")
    if n.type in KINDS and name is not None:
        print(n.type, name.text.decode(), n.start_point[0] + 1, n.end_point[0] + 1)
# functions bound to a name (const f = () => …): a variable_declarator whose "value" is an arrow_function or a function
