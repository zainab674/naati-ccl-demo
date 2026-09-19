"""Deeper end-to-end checks against a running server (python e2e_test.py). Reseed afterwards."""
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


def login(email):
    c = httpx.Client(base_url=BASE, timeout=60)
    r = c.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return c


stu = login("arjun@example.com")
check("bad password rejected", httpx.post(f"{BASE}/api/auth/login", json={"email": "arjun@example.com", "password": "x"}).status_code == 401)
check("unavailable language rejected", stu.patch("/api/me", json={"test_language": "pa"}).status_code == 400)
check("available language accepted", stu.patch("/api/me", json={"test_language": "hi"}).json()["test_language"] == "hi")
check("patching language keeps exam date", stu.patch("/api/me", json={"exam_date": "2026-12-01"}).json()["exam_date"] == "2026-12-01"
      and stu.patch("/api/me", json={"test_language": "hi"}).json()["exam_date"] == "2026-12-01")

# ---- full mock: answer every segment, repeat 3 times in dialogue 1 (1 free -> 2 extra)
mid = stu.post("/api/attempts", json={"mode": "mock", "mock_test_id": "mock-1"}).json()["id"]
st = stu.get(f"/api/attempts/{mid}/state").json()
total = st["total"]
repeats_done = 0
for i in range(total):
    p = stu.post(f"/api/attempts/{mid}/play")
    assert p.status_code == 200, p.text
    if i in (0, 1, 2):
        check(f"repeat allowed on segment {i + 1}", stu.post(f"/api/attempts/{mid}/play").json()["is_repeat"])
        repeats_done += 1
    r = stu.post(f"/api/attempts/{mid}/segments/{i}/audio", files={"audio": ("a.webm", b"\x01" * 4000, "audio/webm")})
    assert r.status_code == 200, r.text
check("last upload finishes the attempt", r.json()["done"])
check("feedback hidden during/after mock", stu.get(f"/api/attempts/{mid}/segments/0/feedback").status_code == 403)
for _ in range(60):
    res = stu.get(f"/api/attempts/{mid}/results").json()
    if res["status"] == "marked":
        break
    time.sleep(0.5)
check("mock fully marked", res["status"] == "marked", res["status"])
d1, d2 = res["dialogues"]
check("dialogue 1 counts 3 repeats", d1["repeats_used"] == 3)
check("extra repeats deducted (2 extra x1 x scale)", abs(d1["repeat_deduction"] - round(2 * d1["scale"] * 2) / 2) < 0.01,
      f'{d1["repeat_deduction"]} scale {d1["scale"]}')
check("total = sum of dialogues", res["total"] == d1["score"] + d2["score"])
expected_pass = res["total"] >= 63 and d1["score"] >= 29 and d2["score"] >= 29
check("pass rule applied (63 + 29 each)", res["passed"] == expected_pass, f'{d1["score"]}+{d2["score"]}={res["total"]} passed={res["passed"]}')
check("every segment has a transcript + marking",
      all(s["response"] and s["response"]["marking"] for d in res["dialogues"] for s in d["segments"]))
check("results never leak to other students", login("priya@example.com").get(f"/api/attempts/{mid}/results").status_code == 404)

# ---- assessor override changes the student's score
adm = login("assessor@example.com")
seg = d2["segments"][0]["response"]
before = res["total"]
adm.post(f"/api/admin/responses/{seg['id']}/override", json={"issues": [], "note": ""})
check("override requires a note", adm.post(f"/api/admin/responses/{seg['id']}/override", json={"issues": [], "note": ""}).status_code == 400)
check("override rejects invalid check", adm.post(f"/api/admin/responses/{seg['id']}/override",
      json={"issues": [{"category": "accuracy", "check": "grammar", "severity": "minor"}], "note": "x"}).status_code == 400)
adm.post(f"/api/admin/responses/{seg['id']}/override",
         json={"issues": [{"category": "accuracy", "check": "distortion", "severity": "critical", "quote": "", "explanation": "Wrong amount"}],
               "note": "Amount interpreted incorrectly"})
after = stu.get(f"/api/attempts/{mid}/results").json()
check("override updates student result", after["total"] < before and after["reviewed_by_assessor"], f"{before} -> {after['total']}")
check("student sees original AI marking too", after["dialogues"][1]["segments"][0]["response"]["ai_marking"] is not None)

# ---- content studio
bad = adm.post("/api/admin/activities", json={"title": "x", "scenario": "", "domain": "Health", "difficulty": "Easy", "script": "EN: hello"})
check("script validation (needs REF + 2 segments)", bad.status_code == 400, bad.json().get("detail", "")[:60])
new = adm.post("/api/admin/activities", json={
    "title": "E2E Pharmacy Visit", "scenario": "Test", "domain": "Health", "difficulty": "Easy",
    "en_role": "Pharmacist", "hi_role": "Customer",
    "script": "EN: Take one tablet twice a day.\nREF: दिन में दो बार एक गोली लें।\nHI: खाने के बाद या पहले?\nREF: After or before food?"}).json()
for _ in range(60):
    row = next(a for a in adm.get("/api/admin/activities").json() if a["id"] == new["id"])
    if row["status"] != "processing":
        break
    time.sleep(1)
check("content studio publishes dialogue", row["status"] == "published", row["status_detail"])
check("new dialogue visible to students", any(a["id"] == new["id"] for a in stu.get("/api/activities").json()))

# ---- protection: key reuse + rate limit
pid = stu.post("/api/attempts", json={"mode": "practice", "activity_id": new["id"]}).json()["id"]
url = stu.post(f"/api/attempts/{pid}/play").json()["url"]
pl = stu.get(url).text
key_url = re.search(r'URI="([^"]+)"', pl).group(1)
codes = [stu.get(key_url).status_code for _ in range(4)]
check("AES key refused after fetch limit", codes[:3] == [200, 200, 200] and codes[3] == 403, str(codes))
seg_url = [l for l in pl.splitlines() if l.startswith("/api/media")][0]
codes = [stu.get(seg_url).status_code for _ in range(70)]
check("rate limit trips on scraping burst", 429 in codes)
check("scraper account flagged", any(u["email"] == "arjun@example.com" for u in adm.get("/api/admin/protection").json()["flagged_users"]))
adm.post("/api/admin/protection/unflag")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
