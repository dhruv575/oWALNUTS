"""Fetch maximum-history daily closes for the top-5 cryptocurrencies from OKX.

Public endpoint, no API key: /api/v5/market/history-candles (paginated with
`after`, newest-first, <=100 rows/request, UTC daily bars). Closes only are
stored. Provenance and SHA-256 recorded by scripts/checksums.py.
"""
import json, time, urllib.request, datetime, pathlib

SYMBOLS = ["BTC-USDT", "ETH-USDT", "XRP-USDT", "BNB-USDT", "SOL-USDT"]
BASE = "https://www.okx.com/api/v5/market/history-candles"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data"

def fetch(inst):
    rows, after = [], ""
    while True:
        url = f"{BASE}?instId={inst}&bar=1Dutc&limit=100" + (f"&after={after}" if after else "")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
        if payload.get("code") != "0":
            raise RuntimeError(f"{inst}: {payload}")
        batch = payload["data"]
        if not batch:
            break
        rows.extend(batch)
        after = batch[-1][0]
        time.sleep(0.15)
    # rows: [ts_ms, o, h, l, c, ...] newest first; keep confirmed bars only (flag field index 8 == "1")
    rows = [r for r in rows if len(r) > 8 and r[8] == "1"]
    rows.sort(key=lambda r: int(r[0]))
    closes = [[datetime.datetime.fromtimestamp(int(r[0]) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d"), float(r[4])] for r in rows]
    return closes

def main():
    OUT.mkdir(exist_ok=True)
    fetched = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for inst in SYMBOLS:
        closes = fetch(inst)
        doc = {"symbol": inst, "source": "OKX /api/v5/market/history-candles bar=1Dutc (confirmed bars)",
               "fetched_utc": fetched, "n": len(closes),
               "first": closes[0][0], "last": closes[-1][0], "closes": closes}
        path = OUT / f"{inst.split('-')[0]}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        print(inst, len(closes), closes[0][0], "->", closes[-1][0])

if __name__ == "__main__":
    main()
