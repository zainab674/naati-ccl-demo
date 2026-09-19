"""End-to-end API smoke test against a running server (python smoke_test.py)."""
import re
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ok = True


def check(label, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra else ""))


s = httpx.Client(base_url=BASE, timeout=30)
r = s.post("/api/auth/login", json={"email": "arjun@example.com", "password": "demo1234"})
check("login", r.status_code == 200)
acts = s.get("/api/activities").json()
check("library lists dialogues", len(acts) >= 6, f"{len(acts)}")
check("library never exposes segment text", "source_text" not in str(acts) and "reference" not in str(acts))

att = s.post("/api/attempts", json={"mode": "practice", "activity_id": acts[-1]["id"]}).json()
aid = att["id"]
st = s.get(f"/api/attempts/{aid}/state").json()
check("state has no text", "source_text" not in str(st))

play = s.post(f"/api/attempts/{aid}/play").json()
url = play["url"]
pl = s.get(url)
check("playlist served to owner", pl.status_code == 200)
check("playlist is AES-128 encrypted", "METHOD=AES-128" in pl.text)
seg_urls = [l for l in pl.text.splitlines() if l.startswith("/api/media") ]
key_url = re.search(r'URI="([^"]+)"', pl.text).group(1)
check("segment served to owner", s.get(seg_urls[0]).status_code == 200)
check("key served to owner", len(s.get(key_url).content) == 16)

anon = httpx.Client(base_url=BASE)
check("copied URL fails without login", anon.get(seg_urls[0]).status_code == 401)
other = httpx.Client(base_url=BASE)
other.post("/api/auth/login", json={"email": "arjun@example.com", "password": "demo1234"})
check("copied URL fails from another session (same user)", other.get(seg_urls[0]).status_code == 403)
check("tampered signature fails", s.get(seg_urls[0].replace("sig=", "sig=0")).status_code == 403)
check("raw media path not reachable", s.get(f"/api/media/{url.split('/')[3]}/enc.key").status_code == 404)

s.post(f"/api/attempts/{aid}/play")  # repeat
r3 = s.post(f"/api/attempts/{aid}/play")
check("third play refused (server-enforced)", r3.status_code == 409)
s2 = s.post("/api/attempts", json={"mode": "practice", "activity_id": acts[-1]["id"]}).json()
check("second tab resumes same attempt, no fresh plays", s2["id"] == aid and s2["resumed"])

up = s.post(f"/api/attempts/{aid}/segments/0/audio", files={"audio": ("a.webm", b"\x00" * 5000, "audio/webm")})
check("upload advances", up.status_code == 200 and up.json()["next_index"] == 1)
check("cannot re-upload old segment", s.post(f"/api/attempts/{aid}/segments/0/audio").status_code == 409)
check("cannot upload unplayed segment", s.post(f"/api/attempts/{aid}/segments/1/audio").status_code == 409)

sub = s.post(f"/api/attempts/{aid}/submit").json()
for _ in range(20):
    res = s.get(f"/api/attempts/{aid}/results")
    if res.status_code == 200 and res.json()["status"] == "marked":
        break
    time.sleep(0.5)
res = res.json()
check("attempt marked", res["status"] == "marked", f"{res['total']}/{res['total_max']}")

adm = httpx.Client(base_url=BASE)
adm.post("/api/auth/login", json={"email": "assessor@example.com", "password": "demo1234"})
check("student cannot use admin", s.get("/api/admin/attempts").status_code == 403)
rows = adm.get("/api/admin/attempts").json()
check("assessor sees attempts", len(rows) >= 4, f"{len(rows)}")
prot = adm.get("/api/admin/protection").json()
check("protection panel: no plain audio on server", prot["sample"]["plain_audio_files_on_server"] == 0)
check("protection panel logged denials", sum(prot["events_24h"].values()) >= 3, str(prot["events_24h"]))
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
