
from flask import Flask, render_template, request, jsonify
import pandas as pd, requests, re, io
from urllib.parse import quote

app = Flask(__name__)

def norm(v):
    if pd.isna(v): return ""
    return re.sub(r"[\s\-]", "", str(v)).upper().strip()

def search_planespotters(reg):
    url = "https://api.planespotters.net/pub/photos/reg/" + quote(norm(reg))
    try:
        r = requests.get(url, headers={"User-Agent":"LogbookPhotoFinder/1.0"}, timeout=15)
        r.raise_for_status()
        return r.json().get("photos", [])
    except Exception:
        return []

def make_jetphotos_url(reg, airport="", year=""):
    # JetPhotos exposes registration search and supports airport/keyword/year filters.
    # We link the user to the source rather than copying protected images.
    params = []
    if airport:
        params.append("keywords=" + quote(str(airport).upper()))
    if year:
        params.append("year=" + quote(str(year)))
    qs = ("?" + "&".join(params)) if params else ""
    return "https://www.jetphotos.com/registration/" + quote(str(reg).upper()) + qs

def photo_info(p):
    src = ""
    if isinstance(p.get("thumbnail"), dict):
        src = p["thumbnail"].get("src","")
    elif isinstance(p.get("thumbnail"), str):
        src = p["thumbnail"]
    link = p.get("link") or p.get("url") or ""
    return {
        "src": src, "link": link,
        "location": p.get("location") or "",
        "photographer": p.get("photographer") or "",
        "date": p.get("date") or p.get("photo_date") or ""
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/parse")
def parse():
    f = request.files.get("file")
    if not f: return jsonify({"error":"Файл не выбран"}), 400
    try:
        df = pd.read_excel(io.BytesIO(f.read()))
    except Exception as e:
        return jsonify({"error":"Не удалось прочитать Excel: " + str(e)}), 400
    needed = ["Date","DepPlace","ArrPlace","Reg"]
    missing = [x for x in needed if x not in df.columns]
    if missing: return jsonify({"error":"Не найдены колонки: " + ", ".join(missing)}), 400

    rows=[]
    for i,r in df.iterrows():
        reg=norm(r["Reg"])
        if not reg: continue
        rows.append({
            "row": int(i)+2,
            "date": "" if pd.isna(r["Date"]) else str(r["Date"]),
            "reg": reg,
            "dep": norm(r["DepPlace"]),
            "arr": norm(r["ArrPlace"]),
            "type": "" if pd.isna(r.get("ACType","")) else str(r.get("ACType","")),
            "flt": "" if pd.isna(r.get("FltTime","")) else str(r.get("FltTime",""))
        })
    return jsonify({"count":len(rows),"rows":rows})

@app.post("/api/photos")
def photos():
    data=request.get_json(force=True)
    reg=data.get("reg","")
    dep=data.get("dep","")
    arr=data.get("arr","")
    date=data.get("date","")
    year = date[-4:] if len(date)>=4 and date[-4:].isdigit() else ""
    raw=search_planespotters(reg)
    result=[]
    for p in raw[:12]:
        x=photo_info(p)
        text=(str(x["location"])+" "+str(x["date"])).upper()
        airport_match = dep in text or arr in text if (dep or arr) else False
        x["airport_match"]=airport_match
        result.append(x)
    # Prioritize airport matches.
    result.sort(key=lambda x: (x["airport_match"],), reverse=True)
    return jsonify({
        "reg":reg,
        "photos":result[:8],
        "jetphotos":make_jetphotos_url(reg, dep or arr, year)
    })

if __name__=="__main__":
    app.run(host="0.0.0.0", port=8501, debug=True)
