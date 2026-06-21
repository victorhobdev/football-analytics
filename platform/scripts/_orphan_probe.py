import json, glob, os
from collections import Counter

known = set()
for f in glob.glob(os.path.join("D:\\open-data\\data\\matches", "**", "*.json"), recursive=True):
    for m in json.load(open(f)):
        known.add(int(m["match_id"]))

orphans = sorted(
    int(os.path.basename(f)[:-5])
    for f in glob.glob(os.path.join("D:\\open-data\\data\\events", "*.json"))
    if int(os.path.basename(f)[:-5]) not in known
)
print("orphans:", len(orphans))

# bundesliga 9/27 known range
b9_27 = []
d = json.load(open(r"D:\open-data\data\matches\9\27.json"))
for m in d:
    b9_27.append(int(m["match_id"]))
lo, hi = min(b9_27), max(b9_27)
print(f"bundesliga 9/27 range: {lo}..{hi}")

in_b9 = [o for o in orphans if lo <= o <= hi]
below = [o for o in orphans if o < lo]
above = [o for o in orphans if o > hi]
print(f"orphans inside bundesliga 9/27 range: {len(in_b9)}")
print(f"orphans below range: {below}")
print(f"orphans above range: {above}")

# reconstruct teams + score for ALL orphans, check sanity
bad = 0
score_samples = []
for mid in orphans:
    d = json.load(open(os.path.join("D:\\open-data\\data\\events", f"{mid}.json")))
    home = away = None
    for e in d:
        if (e.get("type") or {}).get("name") == "Starting XI":
            nm = (e.get("team") or {}).get("name")
            if home is None:
                home = nm
            elif away is None and nm != home:
                away = nm
                break
    # goals per team
    gh = ga = 0
    for e in d:
        if (e.get("type") or {}).get("name") == "Shot":
            if (e.get("shot", {}).get("outcome", {}) or {}).get("name") == "Goal":
                t = (e.get("team") or {}).get("name")
                if t == home:
                    gh += 1
                elif t == away:
                    ga += 1
    if home is None or away is None:
        bad += 1
    if len(score_samples) < 6:
        score_samples.append((mid, home, away, gh, ga))
print("orphans missing home/away:", bad)
print("reconstruction samples (mid, home, away, hg, ag):")
for s in score_samples:
    print("  ", s)

# classify competition for the 2 outliers by team
for mid in (7298, 69143):
    if os.path.exists(os.path.join("D:\\open-data\\data\\events", f"{mid}.json")):
        d = json.load(open(os.path.join("D:\\open-data\\data\\events", f"{mid}.json")))
        teams = sorted({(e.get("team") or {}).get("name") for e in d if (e.get("team") or {}).get("name")})
        print(f"outlier {mid} teams: {teams}")
