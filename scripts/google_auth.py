"""
google_auth.py — OAuth 2.0 token management for CB247 Google data pipelines.
Authenticates as cb_agent@chasingbetter.com.au using desktop-app OAuth credentials.
Supports two modes:
  --console  : Console-based (no browser needed on server)
  default    : Opens browser on local machine

Token is cached in secrets/token.json and auto-refreshed on subsequent runs.
"""

import json
import os
import sys
import tempfile
import argparse
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_DIR = BASE_DIR / "secrets"
OAUTH_JSON = SECRETS_DIR / "google-oauth.json"
TOKEN_FILE = SECRETS_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",    # GA4
    "https://www.googleapis.com/auth/webmasters.readonly",   # GSC
    "https://www.googleapis.com/auth/business.manage",       # Google Business Profile
    "https://www.googleapis.com/auth/adwords",               # Google Ads
]


def get_valid_credentials(console_mode: bool = False) -> Credentials:
    """
    Returns a valid Credentials object. Handles both browser and console auth.
    Forces re-auth if the stored token is missing any required scopes (e.g. after
    adding business.manage to SCOPES).
    """
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_info(
            json.loads(TOKEN_FILE.read_text()),
            scopes=SCOPES
        )
        # If stored scopes don't cover current SCOPES, force a fresh consent flow.
        stored_scopes = set(creds.scopes or [])
        required_scopes = set(SCOPES)
        if not required_scopes.issubset(stored_scopes):
            print("Scope change detected — re-authorization required.", file=sys.stderr)
            print(f"  Missing: {required_scopes - stored_scopes}", file=sys.stderr)
            creds = None  # force fresh auth below

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if console_mode:
                creds = _console_auth()
            else:
                creds = _browser_auth()

    save_token(creds)
    return creds


def _browser_auth() -> Credentials:
    """Opens local browser for OAuth consent."""
    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_JSON), SCOPES)
    return flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline"
    )


def _console_auth() -> Credentials:
    """Console-based auth: prints URL, reads auth code from stdin."""
    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_JSON), SCOPES)
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    print("\n" + "=" * 60)
    print("OPEN THIS URL IN YOUR BROWSER:")
    print("=" * 60)
    print(auth_url)
    print("=" * 60)
    print("\n1. Visit the URL above (make sure you're logged in as")
    print("   cb_agent@chasingbetter.com.au in your browser)")
    print("2. Approve the permissions")
    print("3. Copy the authorization code from the redirect URL")
    print("4. Paste it below and press Enter")
    print("\nAuthorization code: ", end="", flush=True)
    code = input().strip()

    flow.fetch_token(code=code)
    return flow.credentials


def save_token(creds: Credentials) -> None:
    """
    Atomically persist the credential token to secrets/token.json.
    Writes to a temp file first, then renames — prevents corruption if
    the process is killed mid-write, which would lock out all pipelines.
    """
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=SECRETS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
        os.chmod(tmp_path, 0o600)          # owner read/write only before rename
        os.replace(tmp_path, TOKEN_FILE)   # atomic on POSIX
    except Exception:
        os.unlink(tmp_path)                # clean up temp on failure
        raise


def revoke_token() -> None:
    """
    Revoke the token with Google's servers, then delete the local file.
    Revoking remotely invalidates the refresh_token so it can't be reused
    even if someone captured it before deletion.
    """
    if not TOKEN_FILE.exists():
        print("No token file found — nothing to revoke.")
        return
    try:
        import requests as _requests
        creds = Credentials.from_authorized_user_info(
            json.loads(TOKEN_FILE.read_text()),
            scopes=SCOPES
        )
        if creds.token:
            _requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": creds.token},
                timeout=10,
            )
    except Exception as e:
        print(f"Warning: remote revoke failed ({e}) — deleting local token anyway.")
    finally:
        TOKEN_FILE.unlink(missing_ok=True)
        print("Token revoked and deleted. Next run will trigger OAuth consent flow.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CB247 Google OAuth authentication")
    parser.add_argument("--console", action="store_true",
                        help="Use console-based auth (no browser needed)")
    parser.add_argument("--revoke", action="store_true",
                        help="Revoke existing token and exit")
    args = parser.parse_args()

    if args.revoke:
        revoke_token()
        sys.exit(0)

    print("CB247 Google OAuth — authenticating as cb_agent@chasingbetter.com.au...")
    creds = get_valid_credentials(console_mode=args.console)
    print(f"Authenticated. Token expires: {creds.expiry}")
    print(f"Token saved to: {TOKEN_FILE}")