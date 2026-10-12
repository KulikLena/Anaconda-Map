"""Render the LinkedIn bar-race video (1080x1350 MP4) from the running dashboard.

    python manage.py runserver            # in one terminal
    python funds/render_video.py          # in another; needs: pip install playwright && playwright install chromium
                                          # and ffmpeg on PATH

Each frame is drawn by /video's renderAt(t) and captured from the canvas, so the result is smooth
and identical every time (no screen recording).
"""

import base64
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/video"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "real_estate_bar_race.mp4")
FPS = 30


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    frames = Path(tempfile.mkdtemp(prefix="frames_"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.goto(URL)
        page.wait_for_function("window.ready === true", timeout=30000)
        total = page.evaluate("window.TOTAL")
        n = int(round(total * FPS))
        for f in range(n):
            data = page.evaluate(
                "t => { renderAt(t); return document.getElementById('c').toDataURL('image/png'); }", f / FPS
            )
            (frames / f"f{f:05d}.png").write_bytes(base64.b64decode(data.split(",", 1)[1]))
        # still for the post thumbnail: last frame
        shutil.copy(frames / f"f{n - 1:05d}.png", OUT.with_suffix(".png"))
        browser.close()
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "f%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow",
        "-movflags", "+faststart", str(OUT),
    ], check=True)
    shutil.rmtree(frames)
    print(f"Saved {OUT} ({n} frames, {total:.1f} s) and {OUT.with_suffix('.png')}")


if __name__ == "__main__":
    main()
