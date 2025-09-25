import chromadb
from graph_builder import Neo4jConnection # We reuse the connection class

# --- Main Query Engine ---
if __name__ == "__main__":
    # --- The User's Question ---
    # We'll hardcode a question for now.
    user_question = "What is the best way to return JSON data?"

    print(f"--- User Query --- \n{user_question}\n")

    # === Part 1: Semantic Search on Vector DB ===
    print("--- Step 1: Performing Semantic Search on ChromaDB ---")
    chroma_client = chromadb.PersistentClient(path="./db")
    collection = chroma_client.get_collection(name="repo_docstrings")

    # Query the collection to find the 5 most relevant docstrings
    results = collection.query(
        query_texts=[user_question],
        n_results=5
    )

    # Extract the function names from the metadata
    relevant_functions = [
        meta['function_name'] 
        for meta in results['metadatas'][0]
    ]

    print("\nFound most relevant functions based on docstrings:")
    for func in relevant_functions:
        print(f"  - {func}")


    # === Part 2: Structural Search on Knowledge Graph ===
    print("\n--- Step 2: Performing Structural Search on Neo4j ---")
    
    # Connect to Neo4j
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4j-test-123" # Use the password that worked
    db_connection = Neo4jConnection(URI, USER, PASSWORD)
    
    # Find the connections for each relevant function
    for func_name in relevant_functions:
        print(f"\n--- Connections for '{func_name}' ---")
        
        # This Cypher query finds the function and its direct neighbors
        query = """
        MATCH (f:Function {name: $func_name})-[r]-(neighbor)
        RETURN type(r) as relationship_type, neighbor.name as neighbor_name
        """
        
        records = db_connection.run_query(query, {"func_name": func_name})
        
        if not records:
            print("  No connections found in the graph.")
        else:
            for record in records:
                rel_type = record['relationship_type']
                neighbor = record['neighbor_name']
                print(f"  - {rel_type} -> {neighbor}")
                
    # Cleanup
    db_connection.close()