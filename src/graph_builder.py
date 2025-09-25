import os
from neo4j import GraphDatabase
from requests import session
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

# --- Part 1: Neo4j Database Connection Class ---
# This class handles all the communication with your Neo4j database.
class Neo4jConnection:
    def __init__(self, uri, user, password):
        # Establishes the connection to the database
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Successfully connected to Neo4j.")

    def close(self):
        # Closes the connection
        self.driver.close()

    def add_function_node(self, file_path, function_name):
        # This is the main function for adding data to our graph
        with self.driver.session() as session:
            session.execute_write(self._create_function_node, file_path, function_name)
    
    @staticmethod
    def _create_function_node(tx, file_path, function_name):
        # This is a Cypher query, the language for Neo4j.
        # MERGE is a smart command: it creates the node if it doesn't exist,
        # or matches it if it already does. This prevents duplicates.
        query = (
            "MERGE (f:Function {name: $name, file_path: $path}) "
            "RETURN f"
        )
        # We pass the variables to the query to prevent security issues
        tx.run(query, name=function_name, path=file_path)

# --- Part 2: Code Parsing Function ---
# This is your proven recursive logic for finding function names.
def find_function_names(node):
    function_names = set()
    if node.type == 'function_definition':
        name_node = node.child_by_field_name('name')
        if name_node:
            function_names.add(name_node.text.decode('utf8'))
    
    for child in node.children:
        function_names.update(find_function_names(child))
    
    return function_names

# --- Part 3: Main Execution Block ---
# This part runs when you execute 'python src/graph_builder.py'
if __name__ == "__main__":
    # --- Database Configuration ---
    #
    #   <<<<< IMPORTANT! CHANGE THIS PASSWORD! >>>>>
    #
    URI = "neo4j://127.0.0.1:7687"
    USER = "neo4j"
    PASSWORD = "neo4j-test-123"
    
    db_connection = Neo4jConnection(URI, USER, PASSWORD)

    # --- Parser Setup ---
    PYTHON_LANGUAGE = Language(tspython.language())
    parser = Parser(PYTHON_LANGUAGE)
    
    # --- File Walking and Processing ---
    repo_path = os.path.join(os.getcwd(), 'temp', 'flask')
    print(f"Starting to scan repository at: {repo_path}")

    # os.walk will go through every folder and file in the directory
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            # We only care about Python files
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'rb') as f:
                        source_code = f.read()
                    
                    # Parse the file and find all functions
                    tree = parser.parse(source_code)
                    functions = find_function_names(tree.root_node)
                    
                    if functions:
                        print(f"Found {len(functions)} functions in {file_path}. Adding to graph...")
                        for func_name in functions:
                            # For each function found, add a node to the database
                            db_connection.add_function_node(file_path, func_name)

                except Exception as e:
                    print(f"Could not parse or process {file_path}. Error: {e}")

    # --- Cleanup ---
    db_connection.close()
    print("\nGraph building complete!")