import os
import sys
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import git
import threading
import uuid
import json

# Add the src directory to the path so we can import modules
sys.path.append(os.path.dirname(__file__))

from graph_builder import get_parser_for_file, find_functions_and_calls_recursively
from vector_builder import find_docstrings_recursively

# Create FastAPI app instance
app = FastAPI(title="Repository Knowledge Graph API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Both frontend ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global job status tracking
job_statuses = {}
job_repo_mapping = {}  # Track which repo each job is analyzing

# Request models
class RepositoryRequest(BaseModel):
    repo_url: str

# The function signature is now updated to accept the new arguments
def run_analysis_pipeline(repo_url: str, job_id: str, job_statuses: dict):
    """
    The main worker function that runs the entire analysis pipeline and updates its status.
    """
    try:
        # === Step 1: Ingestion (Cloning) ===
        job_statuses[job_id] = "processing: cloning repository"
        print(f"--- [WORKER {job_id}] Step 1/3: Cloning repository... ---")
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        local_path = os.path.join(os.getcwd(), 'temp', repo_name)
        
        if os.path.exists(local_path):
            print(f"Repository already exists at {local_path}. Skipping clone.")
        else:
            git.Repo.clone_from(repo_url, local_path)
        print(f"--- [WORKER {job_id}] Cloning complete. ---")

        # === Step 2: Function Analysis (No Neo4j needed) ===
        job_statuses[job_id] = "processing: analyzing functions"
        print(f"--- [WORKER {job_id}] Step 2/3: Analyzing functions and calls... ---")
        
        supported_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx']
        all_repo_functions = {}
        function_count = 0

        for root, dirs, files in os.walk(local_path):
            for file in files:
                if any(file.endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        parser, language_type = get_parser_for_file(file_path)
                        if parser is None:
                            continue
                        
                        with open(file_path, 'rb') as f:
                            source_code = f.read()
                        tree = parser.parse(source_code)
                        found_items = find_functions_and_calls_recursively(tree.root_node, language_type)
                        
                        if found_items:
                            relative_path = os.path.relpath(file_path, local_path)
                            all_repo_functions[relative_path] = {
                                'language': language_type,
                                'functions': found_items,
                                'full_path': file_path
                            }
                            function_count += len(found_items)
                            print(f"--- [WORKER {job_id}] Found {len(found_items)} functions in {relative_path} ({language_type}) ---")
                            
                    except Exception as e:
                        print(f"--- [WORKER {job_id}] Error processing {file_path}: {e} ---")

        # Save function data to JSON file for later querying
        functions_file = os.path.join(os.getcwd(), 'db', f'{repo_name}_functions.json')
        os.makedirs(os.path.dirname(functions_file), exist_ok=True)
        with open(functions_file, 'w') as f:
            json.dump(all_repo_functions, f, indent=2)
        
        print(f"--- [WORKER {job_id}] Analyzed {function_count} functions across {len(all_repo_functions)} files ---")

        # === Step 3: Documentation Extraction (Simplified) ===
        job_statuses[job_id] = "processing: extracting documentation"
        print(f"--- [WORKER {job_id}] Step 3/3: Extracting documentation... ---")

        doc_count = 0
        all_docs = {}
        
        for root, dirs, files in os.walk(local_path):
            for file in files:
                if any(file.endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        parser, language_type = get_parser_for_file(file_path)
                        if parser is None:
                            continue
                            
                        with open(file_path, 'rb') as f:
                            source_code = f.read()
                        
                        docs = find_docstrings_recursively(parser.parse(source_code).root_node, language_type)
                        if docs:
                            relative_path = os.path.relpath(file_path, local_path)
                            all_docs[relative_path] = {
                                'language': language_type,
                                'docs': docs
                            }
                            doc_count += len(docs)
                            
                    except Exception as e:
                        print(f"--- [WORKER {job_id}] Error processing {file_path} for docs: {e} ---")

        # Save documentation data
        docs_file = os.path.join(os.getcwd(), 'db', f'{repo_name}_docs.json')
        with open(docs_file, 'w') as f:
            json.dump(all_docs, f, indent=2)
        
        print(f"--- [WORKER {job_id}] Extracted {doc_count} documented functions ---")
        
        # This is the final, crucial update
        job_statuses[job_id] = "complete"
        print(f"--- [WORKER {job_id}] Vector index complete. ---")
        print(f"--- [WORKER {job_id}] ANALYSIS FINISHED ---")

    except Exception as e:
        job_statuses[job_id] = "failed"
        print(f"--- [WORKER {job_id}] An error occurred: {e} ---")


# FastAPI endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Repository Knowledge Graph API is running"}

@app.post("/analyze")
async def analyze_repository(request: RepositoryRequest, background_tasks: BackgroundTasks):
    """Start repository analysis"""
    job_id = str(uuid.uuid4())
    job_statuses[job_id] = "queued"
    
    # Run analysis in background
    background_tasks.add_task(run_analysis_pipeline, request.repo_url, job_id, job_statuses)
    
    return {
        "message": "Analysis started", 
        "job_id": job_id,
        "status": "queued"
    }

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in job_statuses:
        return {"error": "Job not found"}, 404
    
    return {
        "job_id": job_id,
        "status": job_statuses[job_id]
    }

@app.get("/jobs")
async def list_jobs():
    """List all jobs and their statuses"""
    return {"jobs": job_statuses}

# Frontend-compatible endpoints
@app.post("/api/v1/ingest")
async def ingest_repository(request: RepositoryRequest, background_tasks: BackgroundTasks):
    """Start repository analysis (frontend-compatible endpoint)"""
    print(f"Received ingest request: {request}")
    print(f"Repository URL: {request.repo_url}")
    
    job_id = str(uuid.uuid4())
    job_statuses[job_id] = "queued"
    
    # Extract repo name from URL
    repo_name = request.repo_url.split('/')[-1]
    job_repo_mapping[job_id] = repo_name
    
    # Run analysis in background
    background_tasks.add_task(run_analysis_pipeline, request.repo_url, job_id, job_statuses)
    
    return {
        "message": "Analysis started", 
        "job_id": job_id,
        "status": "queued"
    }
    
    return {
        "message": "Analysis started", 
        "job_id": job_id,
        "status": "queued"
    }

@app.get("/api/v1/ingest/status/{job_id}")
async def get_ingest_status(job_id: str):
    """Get job status (frontend-compatible endpoint)"""
    if job_id not in job_statuses:
        return {"error": "Job not found"}, 404
    
    return {
        "job_id": job_id,
        "status": job_statuses[job_id],
        "repo_name": job_repo_mapping.get(job_id, "unknown")
    }

@app.get("/api/v1/graph/{repo_name}")
async def get_graph_data(repo_name: str):
    """Get function graph data for visualization"""
    functions_file = os.path.join(os.getcwd(), 'db', f'{repo_name}_functions.json')
    
    if not os.path.exists(functions_file):
        return {"error": "Graph data not found"}, 404
    
    with open(functions_file, 'r') as f:
        functions_data = json.load(f)
    
    # Convert to graph format for visualization
    nodes = []
    edges = []
    
    for file_path, file_data in functions_data.items():
        for func_name, calls in file_data['functions'].items():
            # Add function node
            nodes.append({
                "id": f"{file_path}::{func_name}",
                "label": func_name,
                "file": file_path,
                "language": file_data['language'],
                "type": "function"
            })
            
            # Add edges for function calls
            for call in calls:
                edges.append({
                    "from": f"{file_path}::{func_name}",
                    "to": call,
                    "type": "calls"
                })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_functions": len(nodes),
            "total_files": len(functions_data),
            "total_calls": len(edges)
        }
    }

@app.post("/api/v1/chat/{repo_name}")
async def chat_with_repo(repo_name: str, query: dict):
    """Enhanced RAG with actual source code analysis"""
    question = query.get("question", "").strip()
    
    if not question:
        return {"error": "Question is required"}, 400
    
    # Load function and documentation data
    docs_file = os.path.join(os.getcwd(), 'db', f'{repo_name}_docs.json')
    functions_file = os.path.join(os.getcwd(), 'db', f'{repo_name}_functions.json')
    
    if not os.path.exists(functions_file):
        return {"error": "Repository data not found"}, 404
    
    with open(functions_file, 'r') as f:
        functions_data = json.load(f)
    
    # Load documentation data if available
    docs_data = {}
    if os.path.exists(docs_file):
        with open(docs_file, 'r') as f:
            docs_data = json.load(f)
    
    # Helper function to read source code content
    def get_source_code_snippet(file_path, max_lines=50):
        """Read actual source code content"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) <= max_lines:
                        return ''.join(lines)
                    else:
                        # Return first 30 lines and last 10 lines with separator
                        start_part = ''.join(lines[:30])
                        end_part = ''.join(lines[-10:])
                        return f"{start_part}\n\n... (file continues) ...\n\n{end_part}"
        except Exception as e:
            return f"Could not read file: {str(e)}"
        return "File not found"
    
    # Enhanced analysis function
    def analyze_code_content(file_path, functions_info):
        """Analyze what the code actually does"""
        try:
            if not os.path.exists(file_path):
                return "File not accessible"
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().lower()
            
            # Determine what this file does based on content analysis
            analysis = []
            
            # UI/Component analysis
            if any(keyword in content for keyword in ['jsx', 'tsx', 'component', 'react', 'return (', 'usestate', 'useeffect']):
                ui_patterns = []
                if 'usestate' in content:
                    ui_patterns.append("state management")
                if 'useeffect' in content:
                    ui_patterns.append("side effects/lifecycle")
                if 'onclick' in content or 'onchange' in content:
                    ui_patterns.append("user interactions")
                if 'form' in content:
                    ui_patterns.append("forms")
                if 'button' in content:
                    ui_patterns.append("buttons/actions")
                if 'input' in content:
                    ui_patterns.append("user input")
                if 'fetch' in content or 'api' in content:
                    ui_patterns.append("API calls")
                    
                if ui_patterns:
                    analysis.append(f"UI Component handling: {', '.join(ui_patterns)}")
            
            # API/Backend analysis
            if any(keyword in content for keyword in ['route', 'post', 'get', 'put', 'delete', 'request', 'response']):
                api_patterns = []
                if 'post' in content:
                    api_patterns.append("POST requests")
                if 'get' in content:
                    api_patterns.append("GET requests")
                if 'auth' in content:
                    api_patterns.append("authentication")
                if 'database' in content or 'db' in content:
                    api_patterns.append("database operations")
                    
                if api_patterns:
                    analysis.append(f"API/Backend functionality: {', '.join(api_patterns)}")
            
            # Data handling
            if any(keyword in content for keyword in ['json', 'data', 'array', 'object', 'map', 'filter', 'reduce']):
                data_patterns = []
                if 'json' in content:
                    data_patterns.append("JSON processing")
                if 'map' in content:
                    data_patterns.append("data transformation")
                if 'filter' in content:
                    data_patterns.append("data filtering")
                if 'sort' in content:
                    data_patterns.append("data sorting")
                    
                if data_patterns:
                    analysis.append(f"Data processing: {', '.join(data_patterns)}")
            
            # Business logic patterns
            business_keywords = {
                'auth': 'authentication/authorization',
                'login': 'user login',
                'signup': 'user registration', 
                'dashboard': 'main interface',
                'spending': 'expense tracking',
                'budget': 'budget management',
                'chart': 'data visualization',
                'theme': 'UI theming',
                'settings': 'configuration',
                'profile': 'user profile'
            }
            
            found_business = []
            for keyword, description in business_keywords.items():
                if keyword in content:
                    found_business.append(description)
            
            if found_business:
                analysis.append(f"Business logic: {', '.join(found_business)}")
            
            return "; ".join(analysis) if analysis else "General utility/helper functionality"
            
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    question_lower = question.lower()
    relevant_info = []
    
    # Enhanced search with actual code analysis
    matches = []
    for file_path, file_data in functions_data.items():
        full_path = file_data.get('full_path', file_path)
        file_name = file_path.split('\\')[-1] if '\\' in file_path else file_path.split('/')[-1]
        
        # Calculate relevance score
        score = 0
        matched_reasons = []
        
        # Check file name and path matches
        for keyword in question_lower.split():
            if len(keyword) > 2:
                if keyword in file_name.lower():
                    score += 3
                    matched_reasons.append(f"filename contains '{keyword}'")
                if keyword in file_path.lower():
                    score += 2
                    matched_reasons.append(f"path contains '{keyword}'")
        
        # Check function names
        for func_name in file_data['functions'].keys():
            for keyword in question_lower.split():
                if len(keyword) > 2 and keyword in func_name.lower():
                    score += 2
                    matched_reasons.append(f"function '{func_name}' contains '{keyword}'")
        
        # Analyze what this file actually does
        code_analysis = analyze_code_content(full_path, file_data)
        
        # Check if the analysis matches the question
        for keyword in question_lower.split():
            if len(keyword) > 2 and keyword in code_analysis.lower():
                score += 4  # Higher weight for actual functionality matches
                matched_reasons.append(f"functionality involves '{keyword}'")
        
        if score > 0:
            matches.append({
                'file': file_name,
                'full_path': full_path,
                'functions': file_data['functions'],
                'language': file_data['language'],
                'score': score,
                'analysis': code_analysis,
                'matched_reasons': matched_reasons
            })
    
    if matches:
        # Sort by relevance score
        matches.sort(key=lambda x: x['score'], reverse=True)
        top_matches = matches[:5]
        
        response = f"Here's what I found that's relevant to your question:\n\n"
        
        for i, match in enumerate(top_matches, 1):
            response += f"**{i}. {match['file']}** ({match['language'].title()})\n"
            response += f"📝 **Purpose**: {match['analysis']}\n"
            response += f"🔧 **Functions**: {', '.join(match['functions'].keys())}\n"
            
            if match['matched_reasons']:
                response += f"🎯 **Why relevant**: {', '.join(match['matched_reasons'])}\n"
            
            # Add some actual code context for top matches
            if i <= 2:  # Only for top 2 matches to keep response manageable
                code_snippet = get_source_code_snippet(match['full_path'], 30)
                if len(code_snippet) > 100:  # Only show if we got meaningful content
                    response += f"📄 **Code preview**:\n```{match['language']}\n{code_snippet[:500]}{'...' if len(code_snippet) > 500 else ''}\n```\n"
            
            response += f"📁 **Path**: {match['full_path']}\n\n"
        
        # Add summary
        total_functions = sum(len(match['functions']) for match in top_matches)
        languages = list(set(match['language'] for match in top_matches))
        
        response += f"💡 **Summary**: Found {len(top_matches)} relevant files with {total_functions} functions across {', '.join(languages)} files.\n"
        
        return {
            "question": question,
            "answer": response,
            "context_used": len(top_matches),
            "total_context": len(functions_data)
        }
    
    # No direct matches - provide repository overview with actual insights
    total_functions = sum(len(file_data['functions']) for file_data in functions_data.values())
    total_files = len(functions_data)
    languages = list(set(file_data['language'] for file_data in functions_data.values()))
    
    # Analyze the overall repository structure
    ui_files = []
    api_files = []
    utility_files = []
    
    for file_path, file_data in functions_data.items():
        full_path = file_data.get('full_path', file_path)
        analysis = analyze_code_content(full_path, file_data)
        
        if 'ui component' in analysis.lower() or 'user interface' in analysis.lower():
            ui_files.append(file_path.split('\\')[-1])
        elif 'api' in analysis.lower() or 'backend' in analysis.lower():
            api_files.append(file_path.split('\\')[-1])
        else:
            utility_files.append(file_path.split('\\')[-1])
    
    response = f"I couldn't find specific matches, but here's what I can tell you about the **{repo_name}** repository:\n\n"
    response += f"📊 **Repository Overview:**\n"
    response += f"- {total_functions} functions across {total_files} files\n"
    response += f"- Languages: {', '.join(languages)}\n\n"
    
    if ui_files:
        response += f"🎨 **UI Components** ({len(ui_files)} files): {', '.join(ui_files[:5])}{'...' if len(ui_files) > 5 else ''}\n"
    if api_files:
        response += f"🔌 **API/Backend** ({len(api_files)} files): {', '.join(api_files[:5])}{'...' if len(api_files) > 5 else ''}\n"
    if utility_files:
        response += f"🔧 **Utilities** ({len(utility_files)} files): {', '.join(utility_files[:5])}{'...' if len(utility_files) > 5 else ''}\n"
    
    response += f"\n🔍 **Try these specific questions:**\n"
    response += f"- 'How does user authentication work?'\n"
    response += f"- 'Show me the dashboard components'\n"
    response += f"- 'What does the spending tracker do?'\n"
    response += f"- 'How is data visualization implemented?'\n"
    
    return {
        "question": question,
        "answer": response,
        "context_used": 0,
        "total_context": total_functions
    }

