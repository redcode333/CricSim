"""
run_web.py  —  start the Cricket Sim web server.
Visit http://localhost:8000 in your browser.
"""
from dotenv import load_dotenv
load_dotenv()

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)
