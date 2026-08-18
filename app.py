
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

JETPHOTOS_API = "https://jp.rewis.workers.dev/"

def search_jetphotos(reg, airport, year):
    """Search JetPhotos through an unofficial JSON proxy.
    We query registration + ICAO airport + year, then exact-match
    returned photo metadata by registration, airport and date.
    """
    params = {
        "page": "1",
        "sort-order": "0",
        "keywords-contain": "0",
        "keywords-type": "all",
        "keywords": f"{format_reg(reg)} {airport_icao(airport)}",
        "year": str(year) if year else "all",
    }
    try:
        r = requests.get(JETPHOTOS_API, params=params,
                         headers={"User-Agent":"LogbookPhotoFinder/2.3"},
                         timeout=25)
        r.raise_for_status()
        return r.json().get("photos", [])
    except Exception:
        return []

def search_planespotters(reg):
    try:
        url = "https://api.planespotters.net/pub/photos/reg/" + quote(norm(reg))
        r = requests.get(url, headers={"User-Agent":"LogbookPhotoFinder/2.3"}, timeout=15)
        r.raise_for_status()
        return r.json().get("photos", [])
    except Exception:
        return []

def photo_info(p, source="JetPhotos"):
    thumb = p.get("thumbnailUrl") or p.get("thumbnail") or p.get("imageUrl") or ""
    if isinstance(thumb, dict):
        thumb = thumb.get("src","")
    src = thumb
    link = p.get("photoPageUrl") or p.get("link") or p.get("url") or ""
    date = p.get("photoDate") or p.get("date") or p.get("photo_date") or ""
    return {
        "src": src,
        "link": link,
        "location": p.get("location") or "",
        "photographer": p.get("photographer") or "",
        "date": date,
        "registration": p.get("registration") or "",
        "source": source,
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
    rows = data.get("rows", [])
    results = {}
    for row in rows:
        reg = norm(row.get("reg",""))
        date = row.get("date_iso") or normalize_date(row.get("date",""))
        year = date[:4] if date else ""
        airports = []
        for a in (row.get("dep_icao") or row.get("dep",""), row.get("arr_icao") or row.get("arr","")):
            a = airport_icao(a)
            if a and a not in airports:
                airports.append(a)

        candidates = []
        # Search separately for departure and arrival airports.
        for airport in airports:
            for p in search_jetphotos(reg, airport, year):
                x = photo_info(p, "JetPhotos")
                x["search_airport"] = airport
                candidates.append(x)

        # Fallback: registration-only sources if airport search returns nothing.
        if not candidates:
            for p in search_planespotters(reg)[:12]:
                x = photo_info(p, "PlaneSpotters")
                x["search_airport"] = ""
                candidates.append(x)

        # Exact matching against returned metadata.
        unique=[]
        seen=set()
        for x in candidates:
            key=(x.get("link"),x.get("src"),x.get("date"),x.get("location"))
            if key in seen: continue
            seen.add(key)
            pdate=normalize_date(x.get("date",""))
            loc=str(x.get("location","")).upper()
            preg=norm(x.get("registration",""))
            airport_matches=[a for a in airports if a and a in loc]
            date_match=bool(date and pdate == date)
            reg_match=(not preg) or preg == reg
            score=(50 if date_match else 0)+(35 if airport_matches else 0)+(15 if reg_match else 0)
            x.update({
                "date_match": date_match,
                "airport_matches": airport_matches,
                "reg_match": reg_match,
                "score": score,
                "exact_match": bool(date_match and airport_matches and reg_match),
            })
            unique.append(x)

        unique.sort(key=lambda x:(x["exact_match"], x["score"]), reverse=True)
        results[row.get("row", reg)] = unique[:12]
    return jsonify(results)

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
