#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import secrets


KEY_ID = "local-social-v1"
raw = secrets.token_bytes(32)
encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
print("# Add these lines to .env.local. Never commit that file.")
print("AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID={}".format(KEY_ID))
print(
    "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON='{}'".format(
        json.dumps({KEY_ID: encoded}, separators=(",", ":"))
    )
)
