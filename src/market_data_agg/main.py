"""Main module for the market data aggregation service."""
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health():
    """Return health check status."""
    return {"status": "ok"}

def run_dev():
    """Run the development server."""
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
