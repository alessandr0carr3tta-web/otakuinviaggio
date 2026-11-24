"""Cerca e scarica foto da Wikimedia Commons per i caroselli di @otaku_in_viaggio.
photos/searches.txt  -> chiave|testo da cercare   => photos/search/<chiave>.json + anteprime
photos/requests.txt  -> nome.jpg|Titolo file      => photos/src/<nome.jpg> (1600 px)
"""
import json, os, re, time, urllib.parse, urllib.request
UA = {"User-Agent": "otaku-in-viaggio-photo-fetcher/1.0 (github.com/alessandr0carr3tta-web/otakuinviaggio)"}
API = "https://commons.wikimedia.org/w/api.php?"
OK = re.compile(r"^(CC0|Public domain|PD)", re.I)  # solo foto senza obbligo di citare l'autore

def get(url, tries=6):
    for k in range(tries):  # misure standard di Wikimedia (330/1280) = miniature già pronte, meno blocchi
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == tries - 1: raise
            w = min(int(e.headers.get("Retry-After") or 0) or 5 * (k + 1), 30); print("429, attendo", w, url[:90], flush=True); time.sleep(w)

def api(**p):
    p.update(format="json")
    return json.loads(get(API + urllib.parse.urlencode(p)))

def lines(path):
    if not os.path.exists(path): return []
    return [l.strip().split("|", 1) for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#") and "|" in l]

os.makedirs("photos/search", exist_ok=True); os.makedirs("photos/src", exist_ok=True)
for key, q in lines("photos/searches.txt"):
    if os.path.exists(f"photos/search/{key}.json"): continue
    r = api(action="query", generator="search", gsrnamespace=6, gsrlimit=50, gsrsearch=q,
            prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=330)
    res = []
    for p in (r.get("query") or {}).get("pages", {}).values():
        i = p["imageinfo"][0]; m = i.get("extmetadata", {})
        lic = (m.get("LicenseShortName") or {}).get("value", "")
        if not OK.match(lic) or not re.search(r"\.(jpe?g|png)$", p["title"], re.I) or i["width"] < 1000: continue
        art = re.sub("<[^>]+>", "", (m.get("Artist") or {}).get("value", "")).strip()
        res.append({"title": p["title"][5:], "w": i["width"], "h": i["height"], "license": lic, "author": art[:60], "thumb": i.get("thumburl")})
    res = res[:5]
    for n, x in enumerate(res):
        x["preview"] = f"photos/search/{key}_{n}.jpg"
        try:
            data = get(x.pop("thumb"))
            open(x["preview"], "wb").write(data); time.sleep(2)
        except Exception as e:
            print("ERRORE anteprima", x["title"], e); x["preview"] = None
    json.dump(res, open(f"photos/search/{key}.json", "w"), ensure_ascii=False, indent=1)

for name, title in lines("photos/requests.txt"):
    out = f"photos/src/{name}"
    if os.path.exists(out) and os.path.getsize(out) > 0: continue
    try:
        data = None
        for wid in (1280, 960, 500):  # le foto più piccole di 1280 px vanno chieste in una misura standard inferiore
            try:
                t = api(action="query", prop="imageinfo", iiprop="url", iiurlwidth=wid, titles="File:" + title)
                u = list(t["query"]["pages"].values())[0]["imageinfo"][0]["thumburl"]
                data = get(u, tries=3); break
            except Exception as e2:
                print("riprovo più piccola", wid, e2, flush=True)
        if data: open(out, "wb").write(data)
        print("OK", name, len(data or b""), flush=True)
        time.sleep(2)
    except Exception as e:
        print("ERRORE", title, e, flush=True)
