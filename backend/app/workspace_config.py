"""Environment-backed settings for the SUJAAI workspace tools.

Kept separate from the legacy config module so existing WhatsApp/database
credentials are not rewritten when workspace options are added.
"""
import os

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
WORKSPACE_UPLOAD_MAX_MB = max(1, int(os.getenv("WORKSPACE_UPLOAD_MAX_MB", "8")))
WORKSPACE_MAX_RECORD_BYTES = max(1024, int(os.getenv("WORKSPACE_MAX_RECORD_BYTES", "100000")))
WORKSPACE_MAX_BACKUP_RECORDS = max(1, int(os.getenv("WORKSPACE_MAX_BACKUP_RECORDS", "5000")))
