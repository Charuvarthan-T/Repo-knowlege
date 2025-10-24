# Repository Knowledge Explorer

A full-stack application that analyzes GitHub repositories and provides intelligent insights through function relationship graphs and AI-powered chat.

## Features

- **Multi-language Support**: Analyzes Python, JavaScript, TypeScript, JSX, and TSX files
- **Function Graph Visualization**: Interactive display of function relationships and call patterns
- **AI-Powered Chat**: Ask questions about the codebase and get intelligent responses
- **Real-time Analysis**: Background processing with status tracking
- **Source Code Insights**: Understands actual functionality, not just function names

## Architecture

### Backend (FastAPI)
- **Multi-language AST parsing** using tree-sitter
- **RESTful API** for repository analysis and chat
- **Background job processing** for scalable analysis
- **File-based storage** (no external database dependencies)

### Frontend (Next.js)
- **React-based UI** with TypeScript
- **Real-time status tracking** during analysis
- **Interactive graph visualization** of code structure
- **Chat interface** for repository exploration

## Project Structure

```
├── src/
│   ├── main.py              # FastAPI server with all endpoints
│   ├── graph_builder.py     # Multi-language AST parsing
│   └── vector_builder.py    # Documentation extraction
├── db/                      # Analysis results (auto-generated)
├── temp/                    # Downloaded repositories (auto-generated)
├── requirements.txt         # Python dependencies
└── README.md
```

## Setup

### Backend Setup
1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```

### Frontend Setup
See the `repo-explorer-ui` repository for frontend setup instructions.

## API Endpoints

- `POST /api/v1/ingest` - Start repository analysis
- `GET /api/v1/ingest/status/{job_id}` - Check analysis status  
- `GET /api/v1/graph/{repo_name}` - Get function relationship graph
- `POST /api/v1/chat/{repo_name}` - Chat with repository using RAG

## Example Usage

1. **Submit Repository**: POST to `/api/v1/ingest` with `{"repo_url": "https://github.com/user/repo"}`
2. **Track Progress**: GET `/api/v1/ingest/status/{job_id}` until status is "complete"
3. **Explore Code**: Use the frontend dashboard or API endpoints to explore

## Supported Languages

- **Python** (.py)
- **JavaScript** (.js, .jsx) 
- **TypeScript** (.ts, .tsx)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License
MIT License - see LICENSE file for details.
