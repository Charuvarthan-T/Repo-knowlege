import os
from .graph_builder import Neo4jConnection, find_functions_and_calls_recursively
from .vector_builder import find_docstrings_recursively
import git
import chromadb
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

def run_analysis_pipeline(repo_url: str):
    """
    The main worker function that runs the entire analysis pipeline.
    """
    try:
        # === Step 1: Ingestion (Cloning) ===
        print("--- [WORKER] Step 1/3: Cloning repository... ---")
        # Use a more robust temporary path
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        local_path = os.path.join(os.getcwd(), 'temp', repo_name)
        
        if os.path.exists(local_path):
            print(f"Repository already exists at {local_path}. Skipping clone.")
        else:
            git.Repo.clone_from(repo_url, local_path)
        print("--- [WORKER] Cloning complete. ---")

        # === Step 2: Knowledge Graph Construction ===
        print("--- [WORKER] Step 2/3: Building knowledge graph... ---")
        URI = "neo4j://localhost:7687"
        USER = "neo4j"
        PASSWORD = "testpassword123" # Make sure this is your correct password
        db_connection = Neo4jConnection(URI, USER, PASSWORD)
        
        # --- Parser Setup ---
        PYTHON_LANGUAGE = Language(tspython.language())
        parser = Parser(PYTHON_LANGUAGE)

        all_repo_functions = {}

        # First pass: Discover all functions and create nodes
        for root, dirs, files in os.walk(local_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'rb') as f:
                        source_code = f.read()
                    tree = parser.parse(source_code)
                    found_items = find_functions_and_calls_recursively(tree.root_node)
                    for func_name in found_items.keys():
                        db_connection.add_function_node(file_path, func_name)
                    all_repo_functions[file_path] = found_items
        
        # Second pass: Create relationships
        for file_path, functions in all_repo_functions.items():
            for caller, callees in functions.items():
                for callee in callees:
                    db_connection.add_call_relationship(caller, callee, file_path)
        
        db_connection.close()
        print("--- [WORKER] Knowledge graph complete. ---")

        # === Step 3: Vector Index Construction ===
        print("--- [WORKER] Step 3/3: Building vector index... ---")
        client = chromadb.PersistentClient(path="./db")
        collection = client.get_or_create_collection(name="repo_docstrings", metadata={"hnsw:space": "cosine"})

        for root, dirs, files in os.walk(local_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'rb') as f:
                        source_code = f.read()
                    
                    docs = find_docstrings_recursively(parser.parse(source_code).root_node)
                    if docs:
                        ids = [f"{file_path}:{name}" for name in docs.keys()]
                        documents = list(docs.values())
                        metadatas = [{"file_path": file_path, "function_name": name} for name in docs.keys()]
                        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        
        print("--- [WORKER] Vector index complete. ---")
        print("--- [WORKER] ANALYSIS FINISHED ---")

    except Exception as e:
        print(f"--- [WORKER] An error occurred: {e} ---")
