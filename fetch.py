import csv
import datetime as dt
import io
import json
import pathlib
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).parent
FILE = ROOT / "data" / "latest.json"
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
HEADERS = {"User-Agent": "Mozilla/5.0"}
try:
    old = json.loads(FILE.read_text(encoding="utf-8"))
    items = old.get("items", {})
except (OSError, ValueError):
    items = {}

def get(url, timeout=12):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()

def save_points(key, points, source, url, unit, frequency):
    points = [{"t": str(t), "v": round(float(v), 5)}
              for t, v in points if v is not None]
    if not points:
        raise ValueError("No valid observations")
    items[key] = {
        "value": points[-1]["v"],
        "previous": points[-2]["v"] if len(points) > 1 else None,
        "observed_at": points[-1]["t"],
        "history": points[-100:],
        "source": source,
        "url": url,
        "unit": unit,
        "frequency": frequency
    }

def fred(key, series):
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + series
    for attempt in range(2):
        try:
            raw = get(url)
            rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            points = [
                (r.get("observation_date") or r.get("DATE"), r.get(series))
                for r in rows
                if r.get(series) not in (None, "", ".", "NaN")
            ]
            save_points(key, points, "FRED", url, "%", "日次")
            print(key, "OK")
            return
        except Exception as exc:
            print(key, "attempt", attempt + 1, type(exc).__name__, str(exc)[:120])
            if attempt == 0:
                time.sleep(2)

def yahoo(key, symbol, unit):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol, safe="")
           + "?range=5d&interval=15m")
    try:
        result = json.loads(get(url))
        chart = result["chart"]["result"][0]
        closes = chart["indicators"]["quote"][0]["close"]
        timestamps = chart["timestamp"]
        points = [
            (dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(), v)
            for t, v in zip(timestamps, closes) if v is not None
        ]
        save_points(key, points, "Yahoo Finance（非公式取得）",
                    url, unit, "15分足（配信遅延あり）")
        print(key, "OK")
    except Exception as exc:
        print(key, type(exc).__name__, str(exc)[:120])

jobs = [
    (fred, "us2", "DGS2"),
    (fred, "us10", "DGS10"),
    (fred, "real10", "DFII10"),
    (fred, "vix", "VIXCLS"),
    (yahoo, "dxy", "DX-Y.NYB", "指数"),
    (yahoo, "wti", "CL=F", "USD/bbl"),
    (yahoo, "brent", "BZ=F", "USD/bbl")
]

with ThreadPoolExecutor(max_workers=7) as pool:
    futures = [pool.submit(func, *args) for func, *args in jobs]
    for future in as_completed(futures):
        future.result()

us10, us2 = items.get("us10"), items.get("us2")
if us10 and us2:
    a = {p["t"]: p["v"] for p in us10.get("history", [])}
    b = {p["t"]: p["v"] for p in us2.get("history", [])}
    dates = sorted(set(a) & set(b))
    if dates:
        points = [(date, a[date] - b[date]) for date in dates]
        save_points("curve", points, "FREDから計算", "", "ポイント", "日次")

FILE.parent.mkdir(parents=True, exist_ok=True)
FILE.write_text(
    json.dumps({"fetched_at": NOW, "items": items},
               ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("Available indicators:", list(items))
