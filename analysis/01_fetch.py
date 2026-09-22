"""Download the data basis: every price snapshot of the EFT 1.0 season + reference tables.
Re-runnable; already-downloaded snapshots are skipped.

The snapshots this produces are committed under live-data/, so a normal regenerate
of the price table does not need to run this - only run it if you deliberately want
to pull a different time range or season from the live data scraper.
"""
import json, os, re, subprocess, sys, urllib.request, concurrent.futures as cf
import flealib as F

REPO = F.SOURCE_REPO             # single definition, shared with the artefact's meta
FILE = F.SOURCE_FILE

def enumerate_commits():
    rows, page = [], 1
    while True:
        out = subprocess.run(["gh", "api",
            f"repos/{REPO}/commits?path={FILE}"
            f"&since={F.SEASON_START.date()}T00:00:00Z&until={F.SEASON_END.date()}T00:00:00Z"
            f"&per_page=100&page={page}",
            "--jq", '.[] | .sha + "\t" + .commit.committer.date'],
            capture_output=True, text=True)
        if out.returncode: sys.exit(f"gh api failed: {out.stderr}")
        got = [l for l in out.stdout.splitlines() if l.strip()]
        rows += got
        if len(got) < 100: break
        page += 1
    rows.sort(key=lambda r: r.split("\t")[1])
    F.COMMITS.write_text("\n".join(rows) + "\n")
    return [r.split("\t") for r in rows]

def fetch_snapshots(rows):
    F.SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    def get(r):
        sha, date = r
        p = F.SNAPSHOTS / f"{date.replace(':','-')}_{sha[:8]}.json"
        if p.exists() and p.stat().st_size > 1000: return
        for _ in range(4):
            try:
                urllib.request.urlretrieve(
                    f"https://raw.githubusercontent.com/{REPO}/{sha}/{FILE}", p); return
            except Exception: pass
        print("FAILED", date, file=sys.stderr)
    with cf.ThreadPoolExecutor(16) as ex: list(ex.map(get, rows))

def fetch_reference():
    F.REFERENCE.mkdir(parents=True, exist_ok=True)
    spt = "https://raw.githubusercontent.com/sp-tarkov/server-csharp/refs/heads/main/Libraries/SPTarkov.Server.Assets/SPT_Data/database"
    for url, name in [(f"{spt}/templates/prices.json", "spt_base_prices.json"),
                      (f"{spt}/globals.json",          "globals.json"),
                      ("https://json.tarkov.dev/regular/items_en", "item_names.json")]:
        if not (F.REFERENCE / name).exists():
            urllib.request.urlretrieve(url, F.REFERENCE / name)
    raw = json.load(open(F.REFERENCE / "item_names.json", encoding="utf-8"))
    raw = raw.get("data", raw)
    ids = {k.split()[0]: raw[k] for k in raw if re.fullmatch(r"[0-9a-f]{24} Name", k)}
    json.dump(ids, open(F.REFERENCE / "id_to_name.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"reference ready ({len(ids)} item names)")

if __name__ == "__main__":
    rows = enumerate_commits(); print(f"{len(rows)} commits in season window")
    fetch_snapshots(rows);      print(f"snapshots on disk: {len(os.listdir(F.SNAPSHOTS))}")
    fetch_reference()
