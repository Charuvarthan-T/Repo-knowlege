import os
from neo4j import GraphDatabase
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser


class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Successfully connected to Neo4j.")

    def close(self):
        self.driver.close()

    # RAG part of the code
    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

    def add_function_node(self, file_path, function_name):
        with self.driver.session() as session:
            session.execute_write(self._create_function_node, file_path, function_name)
            
    def add_call_relationship(self, caller_func, callee_func, file_path):
        with self.driver.session() as session:
            session.execute_write(self._create_call_relationship, caller_func, callee_func, file_path)

    @staticmethod
    def _create_function_node(tx, file_path, function_name):
        query = "MERGE (f:Function {name: $name, file_path: $path}) RETURN f"
        tx.run(query, name=function_name, path=file_path)
        
    @staticmethod
    def _create_call_relationship(tx, caller_func, callee_func, file_path):
        query = (
            "MATCH (caller:Function {name: $caller_name, file_path: $path}) "
            "MATCH (callee:Function {name: $callee_name}) "
            "MERGE (caller)-[:CALLS]->(callee)"
        )
        tx.run(query, caller_name=caller_func, callee_name=callee_func, path=file_path)

# --- Part 2: Multi-Language Code Parsing ---

def get_parser_for_file(file_path):
    """Get the appropriate parser based on file extension"""
    if file_path.endswith('.py'):
        language = Language(tspython.language())
        return Parser(language), 'python'
    elif file_path.endswith('.js') or file_path.endswith('.jsx'):
        language = Language(tsjs.language())
        return Parser(language), 'javascript'
    elif file_path.endswith('.ts'):
        language = Language(tsts.language_typescript())
        return Parser(language), 'typescript'
    elif file_path.endswith('.tsx'):
        language = Language(tsts.language_tsx())
        return Parser(language), 'typescript'
    return None, None

def find_functions_and_calls_recursively(node, language_type='python'):
    """Find functions and calls for multiple languages"""
    results = {}
    
    # Language-specific function definition patterns
    function_types = {
        'python': ['function_definition'],
        'javascript': ['function_declaration', 'arrow_function', 'method_definition'],
        'typescript': ['function_declaration', 'arrow_function', 'method_definition', 'function_signature']
    }
    
    # If the current node is a function definition
    if node.type in function_types.get(language_type, []):
        func_name = extract_function_name(node, language_type)
        if func_name:
            # Find all calls WITHIN this function
            calls_in_body = find_calls_in_node(node, language_type)
            results[func_name] = list(calls_in_body)

    # Continue searching through children
    for child in node.children:
        child_results = find_functions_and_calls_recursively(child, language_type)
        for func, calls in child_results.items():
            if func not in results:
                results[func] = []
            results[func].extend(calls)

    return results

def extract_function_name(node, language_type):
    """Extract function name based on language type"""
    if language_type == 'python':
        name_node = node.child_by_field_name('name')
        return name_node.text.decode('utf8') if name_node else None
    
    elif language_type in ['javascript', 'typescript']:
        # Handle different JS/TS function patterns
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            return name_node.text.decode('utf8') if name_node else None
        elif node.type == 'method_definition':
            name_node = node.child_by_field_name('name')
            return name_node.text.decode('utf8') if name_node else None
        elif node.type == 'arrow_function':
            # Arrow functions might not have names, we'll skip them for now
            return None
    
    return None

def find_calls_in_node(node, language_type='python'):
    """Find function calls within a node for multiple languages"""
    call_names = set()
    
    # Language-specific call patterns
    call_types = {
        'python': ['call'],
        'javascript': ['call_expression'],
        'typescript': ['call_expression']
    }
    
    if node.type in call_types.get(language_type, []):
        if language_type == 'python':
            func_identifier_node = node.child_by_field_name('function')
            if func_identifier_node and func_identifier_node.type == 'identifier':
                call_names.add(func_identifier_node.text.decode('utf8'))
        
        elif language_type in ['javascript', 'typescript']:
            func_identifier_node = node.child_by_field_name('function')
            if func_identifier_node and func_identifier_node.type == 'identifier':
                call_names.add(func_identifier_node.text.decode('utf8'))
    
    # Recursively search in children
    for child in node.children:
        call_names.update(find_calls_in_node(child, language_type))
        
    return call_names

# --- Part 3: Main Execution Logic ---
if __name__ == "__main__":
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4j-test-123"
    
    db_connection = Neo4jConnection(URI, USER, PASSWORD)
    
    repo_path = os.path.join(os.getcwd(), 'temp', 'SpendWise')
    print(f"Starting to scan repository at: {repo_path}")

    all_repo_functions = {}
    supported_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx']

    # Pass 1: Discover all functions and create nodes
    print("--- Pass 1: Discovering all functions and creating nodes ---")
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if any(file.endswith(ext) for ext in supported_extensions):
                file_path = os.path.join(root, file)
                try:
                    # Get the appropriate parser for this file type
                    parser, language_type = get_parser_for_file(file_path)
                    if parser is None:
                        continue
                    
                    with open(file_path, 'rb') as f:
                        source_code = f.read()
                    
                    tree = parser.parse(source_code)
                    found_items = find_functions_and_calls_recursively(tree.root_node, language_type)
                    
                    if found_items:
                        print(f"Processing {file_path} ({language_type})...")
                        for func_name in found_items.keys():
                            db_connection.add_function_node(file_path, func_name)
                        
                        all_repo_functions[file_path] = found_items

                except Exception as e:
                    print(f"Could not process {file_path}. Error: {e}")

    # Pass 2: Create relationships
    print("\n--- Pass 2: Creating call relationships ---")
    for file_path, functions in all_repo_functions.items():
        for caller, callees in functions.items():
            for callee in callees:
                db_connection.add_call_relationship(caller, callee, file_path)

    db_connection.close()
    print("\nMulti-language graph building complete with relationships!")