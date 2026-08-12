# Lekki Gardens PH1 Football Tournament

## Run locally

```bash
python3 -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:8502`.

## Supabase setup

1. Open your Supabase SQL editor.
2. Run `supabase/schema.sql` to create the tables.
3. Export these environment variables:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

4. Migrate the current SQLite data into Supabase:

```bash
python scripts/migrate_sqlite_to_supabase.py
```

## Render setup

Use these settings for the Render Web Service:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
```

Add these environment variables on Render:

```bash
FLASK_SECRET_KEY=...
ADMIN_CODE=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

## Notes

- If the Supabase variables are not set, the app falls back to local SQLite for development.
- The admin panel is hidden behind the admin code.
