"""Vercel FastAPI application entrypoint.

Set the Vercel backend project's Root Directory to "backend".
Vercel detects this root-level main.py and sends all paths to the FastAPI
application, allowing its router to handle /api/* endpoints directly.
"""
from app.main import app
