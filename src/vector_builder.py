import os
import chromadb
import tree_sitter_python as tspython
from tree_sitter import Language, Parser


def find_docstrings_recursively(node):
    docstrings = {}
    
    if node.type == 'function_definition':
        func_name_node = node.child_by_field_name('name')
        func_body_node = node.child_by_field_name('body')

        if func_name_node and func_body_node:
            func_name = func_name_node.text.decode('utf8')
            
            first_child = func_body_node.children[0] if func_body_node.children else None
            if first_child and first_child.type == 'expression_statement':
                string_node = first_child.children[0] if first_child.children else None
                if string_node and string_node.type == 'string':
                    docstring_text = string_node.text.decode('utf8').strip().strip('"""').strip("'''")
                    if docstring_text: 
                        docstrings[func_name] = docstring_text
    
    for child in node.children:
        child_docstrings = find_docstrings_recursively(child)
        docstrings.update(child_docstrings)
            
    return docstrings




if __name__ == "__main__":
    client = chromadb.PersistentClient(path="./db")
    collection = client.get_or_create_collection(
        name="repo_docstrings",
        metadata={"hnsw:space": "cosine"}
    )
    print("ChromaDB collection is ready.")

    PYTHON_LANGUAGE = Language(tspython.language())
    parser = Parser(PYTHON_LANGUAGE)
    
    repo_path = os.path.join(os.getcwd(), 'temp', 'flask')
    print(f"Starting to scan repository at: {repo_path}")

    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'rb') as f:
                        source_code = f.read()
                    
                    docs = find_docstrings_recursively(parser.parse(source_code).root_node)
                    
                    if docs:
                        print(f"Found {len(docs)} docstrings in {file_path}. Adding to vector index...")
                        
                        ids = [f"{file_path}:{name}" for name in docs.keys()]
                        documents = list(docs.values())
                        metadatas = [{"file_path": file_path, "function_name": name} for name in docs.keys()]
                        
                        collection.add(
                            ids=ids,
                            documents=documents,
                            metadatas=metadatas
                        )

                except Exception as e:
                    print(f"Could not process {file_path}. Error: {e}")

    print("\nVector index building complete!")
    print(f"Total items in collection: {collection.count()}")