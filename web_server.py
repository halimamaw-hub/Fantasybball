"""
Tiny Flask app whose only job is to give Render something to serve on
Render's free "Web Service" tier, and something for Uptime Robot to ping
every few minutes so Render doesn't spin the service down for inactivity.
It has nothing to do with the draft logic itself.
"""
from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home():
    return "Draft bot is alive."


def _run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    """Starts the Flask server on a background thread so it doesn't block
    the Discord bot's own event loop."""
    t = Thread(target=_run)
    t.daemon = True
    t.start()
