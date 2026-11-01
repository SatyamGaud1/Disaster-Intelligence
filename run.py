"""
Application Entry Point for Disaster Intelligence Platform.
Executes the development server and ensures the SQLite database is initialized.
"""

import os
from app import create_app
from app.database import init_db

app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    # Ensure database schema is ready before running server
    with app.app_context():
        init_db()
        print("[OK] Database checked and ready.")

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "t")

    print("================================================================")
    print(" DISASTER INTELLIGENCE PLATFORM - ACTIVE")
    print(" Multi-Hazard Monitoring and Incident Prioritization Platform")
    print(f" Local URL:   http://127.0.0.1:{port}")
    print(f" Network URL: http://localhost:{port}")
    print("================================================================")

    app.run(host=host, port=port, debug=debug, use_reloader=False)

