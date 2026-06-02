start "Backend" cmd /k "uvicorn backend.main:app --reload --port 8000"
start "Frontend" cmd /k "cd frontend && npm run dev"
