# Place OAuth 2.0 Desktop client JSON here

Download from **GCP Console → APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app**.

Save the downloaded file as:

```
credentials/google-oauth-client.json
```

Or set `GOOGLE_DRIVE_CLIENT_SECRET_FILE` in `.env` to another path.

**Do not commit** the real client secret file — it is listed in `.gitignore`.

See `docs/WSR_GOOGLE_DRIVE_SETUP.md` for full setup steps.
