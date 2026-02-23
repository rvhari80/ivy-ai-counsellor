"""
IVY AI Counsellor - FastAPI app entry point.
"""
from fastapi import FastAPI

app = FastAPI(title="IVY AI Counsellor")


@app.get("/")
async def root():
    return {"message": "IVY AI Counsellor API"}
