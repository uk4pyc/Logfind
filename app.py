
from flask import Flask, render_template, request, jsonify
import pandas as pd, requests, io, re, datetime
import airportsdata
from urllib.parse import quote

app = Flask(__name__)

def norm(v):
    if pd.isna(v): return ""
    return re.sub(r"[\s\-]", "", str(v)).upper().strip()

AIRPORTS = airportsdata.load("ICAO")

def airport_icao(code):
    c = norm(code)
    if len(c) == 4 and c in AIRPORTS:
        return c
    # Excel commonly contains IATA 3-letter codes such as LEJ.
    for icao, a in AIRPORTS.items():
        if str(a.get("iata","")).upper() == c:
            return icao
    return c

def normalize_date(value):
    if not value:
        return ""
    s = str(value).strip()
    dt = pd.to_datetime(s, errors="coerce", dayfirst=False)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return s
    return dt.strftime("%Y-%m-%d")

def format_reg(reg):
    """Format aircraft registrations for human/web searches.
    Example: A9CDHW -> A9C-DHW.
    Existing hyphens are normalized first.
    """
    r = norm(reg)
    if len(r) == 6:
        return r[:3] + "-" + r[3:]
    return r

def search_planespotters(reg):
    try:
        url = "https://api.planespotters.net/pub/photos/reg/" + quote(norm(reg))
        r = requests.get(url, headers={"User-Agent":"LogbookPhotoFinder/2.0"}, timeout=15)
        r.raise_for_status()
        return r.json().get("photos", [])
    except Exception:
        return []

def photo_info(p):
    thumb = p.get("thumbnail")
    src = thumb.get("src","") if isinstance(thumb, dict) else (thumb or "")
    return {
        "src": src,
        "link": p.get("link") or p.get("url") or "",
        "location": p.get("location") or "",
        "photographer": p.get("photographer") or "",
        "date": p.get("date") or p.get("photo_date") or ""
    }

def photo_date_key(value):
    if not value:
        return ""
    return normalize_date(value)

def score_photo(photo, target_date, airport):
    pdate = photo_date_key(photo.get("date",""))
    loc = str(photo.get("location","")).upper()
    airport = airport_icao(airport)
    date_match = bool(target_date and pdate == target_date)
    airport_match = bool(airport and airport in loc)
    score = (50 if date_match else 0) + (40 if airport_match else 0) + 10
    return score, date_match, airport_match

def jetphotos_url(reg, airport="", date=""):
    q = []
    airport = airport_icao(airport)
    if airport: q.append("keywords=" + quote(airport))
    if date: q.append("year=" + quote(str(date)[:4]))
    return "https://www.jetphotos.com/registration/" + quote(format_reg(reg)) + ("?" + "&".join(q) if q else "")

def airliners_url(reg, airport="", date=""):
    terms = " ".join(x for x in [format_reg(reg), airport_icao(airport), normalize_date(date)] if x)
    return "https://www.airliners.net/search?keywords=" + quote(terms)

def google_images_url(reg, airport="", date=""):
    terms = '"{}" "{}" "{}"'.format(format_reg(reg), airport_icao(airport), normalize_date(date))
    return "https://www.google.com/search?tbm=isch&q=" + quote(terms)

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/parse")
def parse():
    f = request.files.get("file")
    if not f:
        return jsonify({"error":"Файл не выбран"}), 400
    try:
        df = pd.read_excel(io.BytesIO(f.read()))
    except Exception as e:
        return jsonify({"error":"Не удалось прочитать Excel: " + str(e)}), 400

    needed = ["Date","DepPlace","ArrPlace","Reg"]
    missing = [x for x in needed if x not in df.columns]
    if missing:
        return jsonify({"error":"Не найдены колонки: " + ", ".join(missing)}), 400

    rows = []
    for i, r in df.iterrows():
        reg = norm(r["Reg"])
        if not reg:
            continue
        rows.append({
            "row": int(i)+2,
            "date": "" if pd.isna(r["Date"]) else str(r["Date"]),
            "date_iso": normalize_date("" if pd.isna(r["Date"]) else str(r["Date"])),
            "reg": reg,
            "display_reg": format_reg(reg),
            "dep": norm(r["DepPlace"]),
            "dep_icao": airport_icao(r["DepPlace"]),
            "arr": norm(r["ArrPlace"]),
            "arr_icao": airport_icao(r["ArrPlace"]),
            "type": "" if pd.isna(r.get("ACType","")) else str(r.get("ACType","")),
            "flt": "" if pd.isna(r.get("FltTime","")) else str(r.get("FltTime",""))
        })
    regs = sorted(set(x["reg"] for x in rows))
    return jsonify({"count": len(rows), "unique_regs": len(regs), "rows": rows})

@app.post("/api/batch")
def batch():
    data = request.get_json(force=True)
    regs = list(dict.fromkeys(data.get("regs", [])))
    out = {}
    for reg in regs:
        raw = search_planespotters(reg)
        out[reg] = [photo_info(p) for p in raw[:12]]
    return jsonify(out)

@app.post("/api/search-links")
def search_links():
    data = request.get_json(force=True)
    reg = norm(data.get("reg",""))
    dep = norm(data.get("dep",""))
    arr = norm(data.get("arr",""))
    date = data.get("date_iso") or data.get("date","")
    airport = airport_icao(dep or arr)
    return jsonify({
        "jetphotos": jetphotos_url(reg, airport, date),
        "airliners": airliners_url(reg, airport, date),
        "google_images": google_images_url(reg, airport, date),
        "planespotters": "https://www.planespotters.net/photos/" + quote(format_reg(reg)),
        "airport_icao": airport
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=True)
