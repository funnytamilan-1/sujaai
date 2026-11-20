"""Vercel serverless entrypoint for the SUJAAI FastAPI application.

The Vercel project root must be the backend directory. Requests under /api/*
are rewritten to this function by backend/vercel.json.
"""
from app.main import app

# Vercel's Python runtime detects the ASGI application named "app".
