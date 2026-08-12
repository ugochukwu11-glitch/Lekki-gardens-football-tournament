# Lekki Gardens PH1 Football Tournament

Run the app locally:

```bash
python app.py
```

Open `http://localhost:5000`.

Set your admin code before deployment:

```bash
export ADMIN_CODE="your-secret-code"
export FLASK_SECRET_KEY="a-long-random-secret"
```

The app creates a local SQLite database at `data/tournament.db` on first run.
