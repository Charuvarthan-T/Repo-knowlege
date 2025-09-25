import os
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv
from graph_builder import Neo4jConnection

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)


if __name__ == "__main__":
    user_question = "What is the best way to return JSON data?"
    print(f"--- User Query --- \n{user_question}\n")

    print("--- Step 1: Retrieving context from databases... ---")
    
    chroma_client = chromadb.PersistentClient(path="./db")
    collection = chroma_client.get_collection(name="repo_docstrings")
    results = collection.query(query_texts=[user_question], n_results=5)
    
    semantic_context = "\n".join(results['documents'][0])
    relevant_function_names = [meta['function_name'] for meta in results['metadatas'][0]]

    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4j-test-123" # The password that worked
    db_connection = Neo4jConnection(URI, USER, PASSWORD)
    
    structural_context = ""
    for func_name in relevant_function_names:
        query = "MATCH (f:Function {name: $func_name})-[r]-(neighbor) RETURN f.name as func, type(r) as rel, neighbor.name as neighbor"
        records = db_connection.run_query(query, {"func_name": func_name})
        for record in records:
            structural_context += f"- {record['func']} -[{record['rel']}]-> {record['neighbor']}\n"
            
    db_connection.close()

    print("\n--- Step 2: Generating answer with LLM ---")
    
    prompt_template = f"""
    You are an expert software engineer assistant. A user has asked a question about a codebase.
    Your task is to answer the user's question based ONLY on the context provided below.
    Do not use any outside knowledge. If the context is not sufficient, say so.

    USER QUESTION:
    "{user_question}"

    CONTEXT FROM SEMANTIC SEARCH (Relevant Docstrings):
    ---
    {semantic_context}
    ---

    CONTEXT FROM KNOWLEDGE GRAPH (Code Connections):
    ---
    {structural_context}
    ---

    FINAL ANSWER:
    """
    
    # 2b. Call the Gemini API with the stable model
    model = genai.GenerativeModel('models/gemini-2.5-flash')
    response = model.generate_content(prompt_template)

    print("\n--- Final Answer ---")
    print(response.text)