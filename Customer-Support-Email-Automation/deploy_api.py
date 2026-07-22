"""
Starts the API + dashboard.

    python deploy_api.py

Then open http://localhost:8000 for the dashboard, http://localhost:8000/docs
for the API docs, or http://localhost:8000/workflow/playground for the raw
Langserve playground.
"""
from dashboard.server import main

if __name__ == "__main__":
    main()
