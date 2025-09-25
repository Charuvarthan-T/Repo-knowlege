import os
from neo4j import GraphDatabase
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

# --- Part 1: Neo4j Database Connection Class ---
class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Successfully connected to Neo4j.")

    def close(self):
        self.driver.close()

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

# --- Part 2: Code Parsing using your proven recursive method ---

def find_functions_and_calls_recursively(node):
    # This dictionary will store { 'function_name': ['call1', 'call2'] }
    results = {}
    
    # If the current node is a function definition, we start a new entry for it
    if node.type == 'function_definition':
        func_name_node = node.child_by_field_name('name')
        func_body_node = node.child_by_field_name('body')
        
        if func_name_node and func_body_node:
            func_name = func_name_node.text.decode('utf8')
            # Find all calls WITHIN the body of this specific function
            calls_in_body = find_calls_in_node(func_body_node)
            results[func_name] = list(calls_in_body)

    # Regardless of the node type, we must continue searching through its children
    for child in node.children:
        # Merge the results from the child nodes into our main results
        child_results = find_functions_and_calls_recursively(child)
        for func, calls in child_results.items():
            if func not in results:
                results[func] = []
            results[func].extend(calls)

    return results

def find_calls_in_node(node):
    # This helper function finds all simple call names within a given node
    call_names = set()
    
    # If the node itself is a call, extract its name
    if node.type == 'call':
        func_identifier_node = node.child_by_field_name('function')
        if func_identifier_node and func_identifier_node.type == 'identifier':
            call_names.add(func_identifier_node.text.decode('utf8'))
    
    # Recursively search in children
    for child in node.children:
        call_names.update(find_calls_in_node(child))
        
    return call_names

# --- Part 3: Main Execution Logic ---
if __name__ == "__main__":
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4j-test-123"
    
    db_connection = Neo4jConnection(URI, USER, PASSWORD)

    PYTHON_LANGUAGE = Language(tspython.language())
    parser = Parser(PYTHON_LANGUAGE)
    
    repo_path = os.path.join(os.getcwd(), 'temp', 'flask')
    print(f"Starting to scan repository at: {repo_path}")

    all_repo_functions = {}

    # Pass 1: Discover all functions and create nodes
    print("--- Pass 1: Discovering all functions and creating nodes ---")
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'rb') as f:
                        source_code = f.read()
                    
                    tree = parser.parse(source_code)
                    found_items = find_functions_and_calls_recursively(tree.root_node)
                    
                    if found_items:
                        print(f"Processing {file_path}...")
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
    print("\nGraph building complete with relationships!")