import csv
import io
import json
import pathlib
import datetime as dt
import urllib.request
import urllib.parse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).parent
FILE = ROOT / "data" / "latest.json"
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
HEADERS = {"User-Agent": "Mozilla/5.0"}

try:
    items = json.loads(FILE.read_text(encoding="utf-8")).get("items", {})
except (OSError, ValueError):
    items = {}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()

def put(key, points, source, url, unit, frequency):
    points = sorted(points, key=lambda p: p[0])
    history = [{"t": t, "v": round(float(v), 5)}
               for t, v in points[-100:]]
    if not history:
        raise ValueError("No observations: " + key)
    items[key] = {
        "value": history[-1]["v"],
        "previous": history[-2]["v"] if len(history) > 1 else None,
        "observed_at": history[-1]["t"],
        "history": history,
        "source": source,
        "url": url,
        "unit": unit,
        "frequency": frequency
    }

def treasury(kind, fields):
    year = dt.datetime.now(dt.timezone.utc).year
    url = (f"https://home.treasury.gov/resource-center/data-chart-center/"
           f"interest-rates/daily-treasury-rates.csv/{year}/all"
           f"?type={kind}&field_tdr_date_value={year}&page&_format=csv")
    rows = list(csv.DictReader(io.StringIO(get(url).decode("utf-8-sig"))))
    for key, column in fields:
        points = []
        for row in rows:
            date = row.get("Date", "").strip()
            value = row.get(column, "").strip()
            if not date or value in ("", "N/A", "."):
                continue
            try:
                day = dt.datetime.strptime(date, "%m/%d/%Y").date().isoformat()
                points.append((day, float(value)))
            except ValueError:
                continue
        put(key, points, "米国財務省", url, "%", "日次")
        print(key, "OK")

def japanese_date(value):
    value = value.strip().replace(" ", "")
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.match(r"^([RHS])([0-9]+)[./-]([0-9]+)[./-]([0-9]+)$", value, re.I)
    if m:
        era, year, month, day = m.groups()
        base = {"R": 2018, "H": 1988, "S": 1925}[era.upper()]
        return dt.date(base + int(year), int(month), int(day)).isoformat()
    raise ValueError("Unknown date: " + value)

def japan():
    url = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"
    raw = get(url)
    text = None
    for encoding in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        raise ValueError("Unknown CSV encoding")
    rows = list(csv.reader(io.StringIO(text)))
    header_index = next(
        (i for i, row in enumerate(rows)
         if any("2年" in cell or "2年" == cell.strip() for cell in row)
         and any("10年" in cell for cell in row)), None)
    if header_index is None:
        raise ValueError("Japan CSV headers not found")
    header = [cell.strip().replace(" ", "") for cell in rows[header_index]]
    cols = {}
    for key, label in (("jp2", "2年"), ("jp10", "10年")):
        cols[key] = next(
            (i for i, name in enumerate(header) if name == label), None)
        if cols[key] is None:
            raise ValueError("Missing column " + label)
    results = {"jp2": [], "jp10": []}
    for row in rows[header_index + 1:]:
        if not row:
            continue
        try:
            date = japanese_date(row[0])
        except (ValueError, IndexError):
            continue
        for key, index in cols.items():
            try:
                value = float(row[index].strip())
                results[key].append((date, value))
            except (ValueError, IndexError):
                continue
    for key, points in results.items():
        put(key, points, "日本財務省", url, "%", "日次")
        print(key, "OK")

def yahoo(key, symbol, unit):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol, safe="")
           + "?range=5d&interval=15m")
    data = json.loads(get(url))["chart"]["result"][0]
    points = [
        (dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(), v)
        for t, v in zip(data["timestamp"],
                        data["indicators"]["quote"][0]["close"])
        if v is not None
    ]
    put(key, points, "Yahoo Finance（非公式取得）", url,
        unit, "15分足（配信遅延あり）")
    print(key, "OK")

jobs = [
    (treasury, "daily_treasury_yield_curve",
     [("us2", "2 Yr"), ("us10", "10 Yr")]),
    (treasury, "daily_treasury_real_yield_curve",
     [("real10", "10 YR")]),
    (japan,),
    (yahoo, "vix", "^VIX", "指数"),
    (yahoo, "dxy", "DX-Y.NYB", "指数"),
    (yahoo, "wti", "CL=F", "USD/bbl"),
    (yahoo, "brent", "BZ=F", "USD/bbl")
]

with ThreadPoolExecutor(max_workers=7) as pool:
    futures = [pool.submit(func, *args) for func, *args in jobs]
    for future in as_completed(futures):
        try:
            future.result()
        except Exception as exc:
            print("Source error:", type(exc).__name__, str(exc)[:200])

a, b = items.get("us10"), items.get("us2")
if a and b and a.get("source") == "米国財務省" and b.get("source") == "米国財務省":
    x = {p["t"]: p["v"] for p in a.get("history", [])}
    y = {p["t"]: p["v"] for p in b.get("history", [])}
    dates = sorted(set(x) & set(y))
    if dates:
        put("curve", [(d, x[d] - y[d]) for d in dates],
            "米国財務省データから計算", "", "ポイント", "日次")

FILE.parent.mkdir(parents=True, exist_ok=True)
FILE.write_text(
    json.dumps({"fetched_at": NOW, "items": items},
               ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("Available:", list(items))
