#!/usr/bin/env python3
"""Récupère les flux RSS, dédoublonne et classe les articles HBC Nantes."""
from __future__ import annotations
import html, json, re, sys, unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data.json"
SEED = Path(__file__).resolve().parent / "seed.json"
PARIS = ZoneInfo("Europe/Paris")
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
UA = "Mozilla/5.0 (compatible; HBCNantesVeille/1.0; +https://github.com/)"
FEEDS = [
    ("Google Actualités", "https://news.google.com/rss/search?q=" + quote_plus('HBC Nantes') + "&hl=fr&gl=FR&ceid=FR:fr"),
    ("Google Actualités", "https://news.google.com/rss/search?q=" + quote_plus('site:handnews.fr "HBC Nantes"') + "&hl=fr&gl=FR&ceid=FR:fr"),
    ("HandNews", "https://handnews.fr/feed/"),
]
THEMES = ["Résultats", "Coupes", "Calendrier", "Effectif", "Club/Polémique"]
WORDS = {
    "Coupes": ["coupe de france", "coupe d'europe", "ehf", "ligue des champions", "quart de finale", "tirage au sort"],
    "Résultats": ["victoire", "victorieux", "autoritaire", "carton", "s'impose", "s’impose", "succès", "défaite", "s'incline", "s’incline", "bat ", "battu", "score", "étrille", "écrasé", "résultat"],
    "Calendrier": ["calendrier", "prochain match", "réception de", "déplacement à", "match contre", "journée", "à venir"],
    "Effectif": ["transfert", "recrute", "renfort", "arrivée", "arrivee", "prolongation", "entraîneur", "entraineur", "coach", "blessé", "blessure", "forfait", "entraîneur", "entraineur", "joueur", "effectif"],
    "Club/Polémique": ["boycott", "polémique", "polemic", "conférence", "conférence", "direction", "club choisit", "controverse"],
}
HIGH_RISK = ["boycott", "polémique", "polemic", "controverse", "accusation", "plainte"]

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))

def text_of(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()

def category(title: str, summary: str) -> str:
    t = norm(title + " " + summary)
    # Thematic priority avoids classifying a cup result as just a league result.
    for name in THEMES:
        if any(norm(w) in t for w in WORDS[name]):
            return name
    return "Club/Polémique"

def relevance(theme: str, title: str, published: datetime) -> int:
    age = (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 86400
    score = 5 if age <= 2 and theme in ("Résultats", "Coupes", "Club/Polémique") else 4 if age <= 7 else 3
    if theme in ("Effectif", "Club/Polémique") and score == 5:
        score = 4  # personal/controversial news should not be promoted automatically
    return score

def parse_date(raw: str) -> datetime:
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def read_feed(name: str, url: str) -> list[dict]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urlopen(req, timeout=25) as response:
        root = ET.fromstring(response.read())
    entries = root.findall(".//item")
    if not entries:
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    records=[]
    for item in entries:
        def val(*paths):
            for path in paths:
                e=item.find(path)
                if e is not None:
                    return e.get("href", "") if e.tag.endswith("link") and e.get("href") else (e.text or "")
            return ""
        title=text_of(val("title", "{http://www.w3.org/2005/Atom}title"))
        link=val("link", "{http://www.w3.org/2005/Atom}link")
        desc=text_of(val("description", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"))
        rawdate=val("pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated")
        if not title or not link or not link.startswith("https://"): continue
        combined=norm(title+" "+desc)
        # Écarter les articles génériques sur le FC Nantes : il faut un signal
        # HBC/Nantes ou handball/Nantes dans le titre/la description.
        has_hbc = "hbc" in combined and "nantes" in combined
        has_handball = "handball" in combined and "nantes" in combined
        if not (has_hbc or has_handball): continue
        # Les résultats de recherche Google sont fréquemment de simples articles
        # d'actualité sans rapport direct; rejeter les correspondances contextuelles.
        title_norm=norm(title)
        if name == "Google Actualités" and not ("hbc" in title_norm and "nantes" in title_norm):
            continue
        published=parse_date(rawdate)
        # Publisher label as embedded in Google News titles; otherwise feed name.
        source=name
        source_el=item.find("source")
        if source_el is not None and source_el.text:
            source=source_el.text.strip()
        if urlparse(link).hostname == "news.google.com":
            original=parse_qs(urlparse(link).query).get("url", [])
            if original and original[0].startswith("https://"):
                link=original[0]
        if name == "Google Actualités" and source == name and " - " in title:
            source=title.rsplit(" - ",1)[1].strip() or name
            title=title.rsplit(" - ",1)[0].strip()
        records.append({"title":title,"url":link,"summary":desc,"source":source,"published":published})
    return records

def draft_tweets(articles: list[dict]) -> list[dict]:
    out=[]
    for a in articles[:6]:
        if not a.get("sources"): continue
        risky=a["theme"] in ("Club/Polémique", "Effectif") or any(w in norm(a["title"]) for w in HIGH_RISK)
        out.append({"theme":a["theme"],"text":f"{a['title']}. À lire dans la source avant tout partage. 🤾","source":a["sources"][0]["name"],"url":a["sources"][0]["url"],"risk":"Élevé" if risky else "À vérifier","riskType":"high" if risky else "medium"})
    return out

def run() -> dict:
    now=datetime.now(timezone.utc)
    if "--if-due" in sys.argv and now.astimezone(PARIS).hour not in (9, 17):
        print(f"Ignoré : {now.astimezone(PARIS):%H:%M} à Paris, hors fenêtre 09h/17h.")
        return {}
    fetched=[]; errors=[]
    for source,url in FEEDS:
        try:
            batch=read_feed(source,url); fetched.extend(batch)
            print(f"OK {source}: {len(batch)} entrée(s)")
        except Exception as exc:
            errors.append(f"{source}: {type(exc).__name__}: {exc}")
            print(f"ÉCHEC {source}: {type(exc).__name__}: {exc}",file=sys.stderr)
    # Exact normalized-title dedup. Keep the first URL/date and merge distinct publishers.
    dedup={}
    for rec in fetched:
        key=re.sub(r"[^a-z0-9]+", " ", norm(rec["title"])).strip()
        if not key: continue
        if key not in dedup: dedup[key]=rec
        elif dedup[key]["source"] != rec["source"]:
            # Preserve genuine source choices for a card.
            dedup[key].setdefault("other_sources",[]).append({"name":rec["source"],"url":rec["url"]})
    articles=[]
    for idx,r in enumerate(dedup.values()):
        theme=category(r["title"],r["summary"])
        pub=r["published"]
        src=[{"name":r["source"],"url":r["url"]}]+r.get("other_sources",[])
        articles.append({"id":f"rss-{idx+1}","date":pub.astimezone(PARIS).strftime("%d %b %Y"),"dateSort":pub.strftime("%Y-%m-%d"),"relevance":relevance(theme,r["title"],pub),"theme":theme,"title":r["title"],"summary":r["summary"] or "Résumé non fourni dans le flux RSS.","sources":src,"confirmation":"Article du flux RSS","confirmationType":"reported"})
    # Pertinence décroissante, puis date récente d'abord (date ISO).
    articles.sort(key=lambda a:(-a["relevance"], tuple(-int(x) for x in a["dateSort"].split("-"))))
    # Garder les 40 meilleurs articles pour une page lisible malgré les gros flux Google News.
    articles=articles[:40]
    provenance="flux RSS récupéré" if articles else "aucun flux RSS accessible"
    if not articles:
        # Keep the last successful snapshot if available; on first run use the actual static-dashboard data.
        previous=None
        try:
            previous=json.loads(OUTPUT.read_text(encoding="utf-8"))
        except Exception: pass
        if previous and previous.get("articles"):
            articles=previous["articles"]
            provenance="flux RSS indisponible — conservation de la dernière veille"
        else:
            seed=json.loads(SEED.read_text(encoding="utf-8"))
            articles=seed["articles"]
            provenance="flux RSS indisponible — données reprises du dashboard statique du 3 novembre 2026"
    seed=json.loads(SEED.read_text(encoding="utf-8"))
    grouped={name:[] for name in THEMES}
    for a in articles:
        if a["theme"] in grouped and len(grouped[a["theme"]])<6:
            grouped[a["theme"]].append(a["title"])
    topics=[{"name":name,"items":items} for name,items in grouped.items() if items]
    # Static calendar and tasks are carried forward from the provided dashboard.
    local_now=now.astimezone(PARIS)
    edition=f"{DAYS_FR[local_now.weekday()]} {local_now.day} {MONTHS_FR[local_now.month-1]} {local_now.year}, {local_now:%Hh%M}"
    data={"edition":edition,"lastUpdated":local_now.strftime("%d/%m/%Y à %H:%M (heure de Paris)"),"nextUpdate":"09h00 et 17h00 (heure de Paris)","articles":articles,"topics":topics,"tweets":draft_tweets(articles),"tasks":seed.get("tasks",[]),"matches":seed.get("matches",[]),"provenance":provenance,"feedErrors":errors,"feedCount":len(FEEDS)}
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Écrit {OUTPUT.name}: {len(articles)} article(s); provenance: {provenance}")
    return data

if __name__ == "__main__":
    run()
