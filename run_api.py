"""FastAPI development server launcher.

Usage:
    python run_api.py

The server will start on http://localhost:8000
API docs available at http://localhost:8000/docs
"""

import uvicorn

if __name__ == "__main__":
    print("Starting FastAPI server...")
    print("API docs: http://localhost:8000/docs")
    print("Health check: http://localhost:8000/health")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(
        "src.interfaces.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )
