# Publishing the dashboard on PythonAnywhere

The published site is a frozen snapshot: it reads `Main data file.xlsx` once and pages do not poll for changes.
On your laptop nothing changes: live editing works as before.

## 1. Before uploading

1. In `config/settings.py`, remove the line `MAPBOX_TOKEN = "pk...."` (keep the `os.environ.get` line above it).
   The token will be set on the server instead, so it never sits in the code.
2. In Mapbox (account.mapbox.com → Tokens), restrict the token's URLs to
   `https://YOURNAME.pythonanywhere.com` and `http://127.0.0.1:8000` (for local use).
3. Do not upload `venv/`, `db.sqlite3`, the EPRA PDFs or other working files.

## 2. Upload the code

Easiest: upload the folder as a zip in the **Files** tab and unzip it in a Bash console
(`unzip "Anaconda Map.zip" -d ~/anaconda`). Or push the folder to GitHub and `git clone` it.

What the site needs: `manage.py`, `config/`, `funds/`, `projects/`, `requirements.txt`, `Main data file.xlsx`.

## 3. Virtualenv

In a PythonAnywhere **Bash console**:

```bash
mkvirtualenv anaconda --python=python3.13      # Django 6.1 needs Python 3.12 or newer
cd ~/anaconda
pip install -r requirements.txt
```

If Python 3.12+ is not offered on your account, tell me: the code also runs on Django 5.2 LTS
(change `Django==6.1.1` to `Django==5.2.*` in requirements.txt).

## 4. Web app

**Web** tab → *Add a new web app* → **Manual configuration** → same Python version.

- **Virtualenv:** `/home/YOURNAME/.virtualenvs/anaconda`
- **Source code / working directory:** `/home/YOURNAME/anaconda`
- **Static files:** URL `/static/` → directory `/home/YOURNAME/anaconda/staticfiles`

Edit the **WSGI configuration file** (link on the Web tab) so it contains only:

```python
import os, sys
path = "/home/YOURNAME/anaconda"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "0"
os.environ["DJANGO_ALLOWED_HOSTS"] = "YOURNAME.pythonanywhere.com"
os.environ["DJANGO_SECRET_KEY"] = "PASTE-A-LONG-RANDOM-STRING"
os.environ["LIVE_RELOAD"] = "0"
os.environ["MAPBOX_TOKEN"] = "pk.your_public_token"
os.environ["GA_MEASUREMENT_ID"] = "G-XXXXXXXXXX"      # or "" to switch analytics off

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

A random secret key: in the Bash console run
`python -c "import secrets; print(secrets.token_urlsafe(50))"`.

## 5. Static files and start

```bash
cd ~/anaconda
python manage.py collectstatic --noinput
```

Then press **Reload** on the Web tab and open `https://YOURNAME.pythonanywhere.com`.

## 6. Updating the data later

Upload the new `Main data file.xlsx` over the old one (Files tab), then press **Reload**.

## Checklist before posting on LinkedIn

- Page opens on the "Funds + listed real estate" view with the takeaway line at the top.
- Map shows (if not: token missing or not allowed for the site URL).
- Open it on your phone: the page scrolls, two fingers move the map.
- Cookie banner appears once; after "Allow", visits show in Google Analytics → Realtime.
