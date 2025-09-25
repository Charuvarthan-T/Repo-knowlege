import os

# entire package for python grammar
import tree_sitter_python as tspython
from tree_sitter import Language, Parser


# initialize the setup
print("Loading Python grammar...")
PYTHON_LANGUAGE = Language(tspython.language())
parser = Parser(PYTHON_LANGUAGE)



# builds ast on the text format of the enitire python file
file_to_parse = os.path.join(os.getcwd(), 'temp', 'flask', 'src', 'flask', 'app.py')
print(f"Attempting to parse file: {file_to_parse}")


try:
    with open(file_to_parse, 'rb') as f:
        source_code = f.read()

except FileNotFoundError:
    print(f"Error: The file '{file_to_parse}' was not found.")
    print("Please make sure you have run 'python src/ingest.py' first.")
    exit()



tree = parser.parse(source_code)
root_node = tree.root_node



# this function traverses the AST to find function definitions
def find_function_names(node, source):
    function_names = set()
    
    if node.type == 'function_definition':
        name_node = node.child_by_field_name('name')
        if name_node:
            function_names.add(name_node.text.decode('utf8'))
    
    for child in node.children:
        function_names.update(find_function_names(child, source))
    
    return function_names

print("\nFound Functions: ")
function_names = find_function_names(root_node, source_code)

if not function_names:
    print("No functions found.")
else:
    for name in sorted(list(function_names)):
        print(name)

print("\nParsing complete")