"""Render locally reviewed evidence. No LLM call, API write or inferred visual assessment."""

import base64
import hashlib
import html
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlparse

from meta_ads_manager.creative_media import walk
from meta_ads_manager.creative_review import number, ratio
from meta_ads_manager.errors import AppError


def read_json(path):
    return json.loads(path.read_text())


def scoped(document, collection, period=False):
    keys = ("client_id", "account_id", "since", "until") if period else ("client_id", "account_id")
    if any(document.get(k) != collection[k] for k in keys):
        raise AppError("SCOPE_MISMATCH", "Ocena lub materiał nie pasuje do raportu.", 3)


def checked_file(directory, relative, digest):
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise AppError("SCOPE_MISMATCH", "Plik dowodu poza katalogiem raportu lub niedostępny.", 3)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise AppError("EVIDENCE_CHANGED", "Plik dowodu zmienił się od oceny.", 3)
    return path


def fmt(value, places=2):
    if value is None:
        return "—"
    rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{rounded:,.{places}f}".replace(",", " ").replace(".", ",")


def render_report(args):
    p = args.directory
    c, media, assessment, review = [
        read_json(f)
        for f in (
            p / "collection.json",
            p / "media.json",
            args.assessment,
            args.notes,
        )
    ]
    if (c["client_id"], c["account_id"]) != (args.client, args.account):
        raise AppError("SCOPE_MISMATCH", "Inne konto w kolekcji kreacji.", 3)
    scoped(media, c)
    scoped(assessment, c, True)
    scoped(review, c, True)
    ids = c["selected_ad_ids"]
    for document in (media, assessment, c):
        found = [x["ad_id"] for x in document["cards"]]
        if len(found) != len(set(found)) or set(found) != set(ids):
            raise AppError("INCOMPLETE_DATA", "Karty nie odpowiadają wybranej próbie.", 5)
    if any(x not in ids for x in review.get("ad_notes", {})):
        raise AppError("SCOPE_MISMATCH", "Komentarz dotyczy reklamy spoza próby.", 3)
    for file, digest in c["source_hashes"].items():
        checked_file(p, file, digest)
    ads, groups = {}, {}
    for ad_id in ids:
        ad = read_json(p / f"ad-{ad_id}.json")["data"]
        if ad["id"] != ad_id or ad["account_id"] != c["account_id"][4:]:
            raise AppError("SCOPE_MISMATCH", "Niezgodna tożsamość reklamy.", 3)
        ads[ad_id] = ad
        goal = ad.get("adset", {}).get("optimization_goal", "UNKNOWN")
        group = groups.setdefault(
            goal,
            {
                "ads": 0,
                "spend": Decimal(0),
                "reported_native_leads": Decimal(0),
                "ads_with_reported_native_leads": 0,
            },
        )
        card = next(x for x in c["cards"] if x["ad_id"] == ad_id)
        group["ads"] += 1
        group["spend"] += number(card["current"]["spend"])
        lead = card["current"]["native_leads_7d_click"]
        if lead is not None:
            group["reported_native_leads"] += number(lead)
            group["ads_with_reported_native_leads"] += 1
    rows = read_json(p / "ads-current.json")["data"]
    account_spend = sum((number(r["spend"]) for r in rows), Decimal(0))
    sample_spend = sum((number(x["current"]["spend"]) for x in c["cards"]), Decimal(0))
    stats = {
        "account_ads": len(rows),
        "sample_ads": len(ids),
        "account_spend": str(account_spend),
        "sample_spend": str(sample_spend),
        "spend_coverage_percent": ratio(sample_spend, account_spend, 100),
        "groups": {
            k: {f: str(v) if isinstance(v, Decimal) else v for f, v in g.items()}
            for k, g in groups.items()
        },
    }
    for group in stats["groups"].values():
        if group["ads_with_reported_native_leads"] == 0:
            group["reported_native_leads"] = None
    e = html.escape
    title = review["title"]
    subtitle = (
        f"{c['since']} – {c['until']} · {c['account']['name']} · {c['account']['timezone_name']}"
    )
    lead = (
        f"Próba: {len(ids)} z {len(rows)} reklam. Wydatki próby: {fmt(sample_spend)} "
        f"{c['account']['currency']}, "
        f"czyli {fmt(stats['spend_coverage_percent'])}% wydatków konta. "
        "Dobór celowy; wyniku próby nie należy uogólniać na całe konto."
    )
    md = [f"# {title}", subtitle, lead]
    logo = base64.b64encode(
        (Path(__file__).parent / "assets/bluerank-logo.png").read_bytes()
    ).decode()
    parts = [
        f'<header><img class="logo" alt="Bluerank" src="data:image/png;base64,{logo}">'
        f'<p class="eyebrow">ANALIZA KREACJI · PILOTAŻ</p><h1>{e(title)}</h1>'
        f"<p>{e(subtitle)}</p><p>{e(lead)}</p>"
        '<a href="#gallery">Przejdź do galerii  →</a></header>'
    ]
    for section in review["sections"]:
        md.extend([f"## {section['title']}", *section["paragraphs"]])
        parts.append(
            f"<section><h2>{e(section['title'])}</h2>"
            + "".join(f"<p>{e(text)}</p>" for text in section["paragraphs"])
            + "</section>"
        )
    for source in review.get("sources", []):
        url = source["url"]
        if urlparse(url).scheme != "https" or not urlparse(url).hostname:
            raise AppError("VALIDATION_ERROR", "Źródło wymaga adresu HTTPS.", 2)
        parts.append(f'<p>Źródło metodyczne: <a href="{e(url, quote=True)}">'
                     f'{e(source["title"])}</a>.</p>')
        md.append(f'Źródło metodyczne: [{source["title"]}]({url}).')
    parts.append(
        '<section id="gallery"><h2>Galeria i karty reklam</h2>'
        '<p>Materiały są dostępne po kliknięciu. '
        "Kolejność plików w galerii nie oznacza kolejności kart "
        "ani konkretnego wariantu emisji.</p>"
        "<nav>"
        + " ".join(f'<a href="#ad-{i}">{i}</a>' for i in range(1, len(ids) + 1))
        + "</nav></section>"
    )
    a_by_id = {x["ad_id"]: x for x in assessment["cards"]}
    m_by_id = {x["ad_id"]: x for x in media["cards"]}
    for i, card in enumerate(c["cards"], 1):
        ad_id = card["ad_id"]
        a, ad, m = a_by_id[ad_id], ads[ad_id], card["current"]
        if a.get("content_status") not in ("partial", "reviewed_images_and_text", "unavailable"):
            raise AppError("VALIDATION_ERROR", "Karta nie ma zakończonej oceny dostępności.", 2)
        checked_file(p, a["source_file"], a["source_sha256"])
        for ref in a["evidence"]:
            checked_file(p, ref["file"], ref["sha256"])
        goal = ad.get("adset", {}).get("optimization_goal", "UNKNOWN")
        label = f"{i}. {a['concept']}"
        identity = f"{ad['name']} · ad_id {ad_id} · {goal}"
        scope_text = f"Kampania: {ad['campaign']['name']}. Zestaw: {ad['adset']['name']}."
        md.extend([f"## {label}", identity, scope_text, a["coverage"]])
        parts.append(
            f'<article id="ad-{i}"><h2>{e(label)}</h2><p class="meta">{e(identity)}</p>'
            f'<p class="meta">{e(scope_text)}</p><p class="coverage">{e(a["coverage"])}</p>'
        )
        assets = [x for x in m_by_id[ad_id]["assets"] if x["status"] == "available"]
        images = [x for x in assets if x["mime"].startswith("image/")]
        main = [x for x in images if x["role"] == "image"] or images
        gallery = []
        seen = set()
        for asset in main:
            if asset["sha256"] in seen:
                continue
            seen.add(asset["sha256"])
            if not re.fullmatch(r"[a-f0-9]{64}\.(jpg|png|webp)", asset["file"]):
                raise AppError("VALIDATION_ERROR", "Niepoprawna nazwa materiału.", 2)
            checked_file(p, "media/" + asset["file"], asset["sha256"])
            relative = "media/" + asset["file"]
            gallery.append(
                f'<a href="{relative}"><img loading="lazy" alt="Materiał reklamy {i}" '
                f'src="{relative}"></a>'
            )
            md.append(f"[Materiał {len(seen)}]({relative})")
        parts.append('<div class="gallery">' + "".join(gallery) + "</div>")
        values = [
            ("Wydatki (" + c["account"]["currency"] + ")", fmt(m["spend"])),
            ("Wyświetlenia", fmt(m["impressions"], 0)),
            ("CTR linku (%)", fmt(m["link_ctr_percent"])),
            ("Częstotliwość", fmt(m["frequency"])),
            ("Leady formularzowe · 7 dni po kliknięciu", fmt(m["native_leads_7d_click"], 0)),
            ("CPL formularza (" + c["account"]["currency"] + ")", fmt(m["native_cpl_7d_click"])),
        ]
        md.append(
            "| Metryka | Wynik |\n| --- | --- |\n" + "\n".join(f"| {k} | {v} |" for k, v in values)
        )
        parts.append(
            "<dl>"
            + "".join(f"<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in values)
            + "</dl>"
        )
        prev = card.get("previous")
        previous_text = (
            f"Poprzedni okres: {c['previous_since']} – {c['previous_until']}. "
            f"Wydatki: {fmt(prev['spend'])} {c['account']['currency']}; "
            f"leady formularzowe: {fmt(prev['native_leads_7d_click'], 0)}; "
            f"CPL: {fmt(prev['native_cpl_7d_click'])} {c['account']['currency']}."
            if prev
            else "Brak wiersza reklamy w poprzednim okresie; nie zastępujemy go zerami."
        )
        parts.append(f'<p class="meta">{e(previous_text)}</p>')
        md.append(previous_text)
        for label, texts in [
            ("Ocena treści", a["observations"]),
            (
                "Wynik i interpretacja",
                [review.get("ad_notes", {}).get(ad_id, "Brak dodatkowej interpretacji wyników.")],
            ),
            ("Propozycja do sprawdzenia", a["hypotheses"]),
        ]:
            parts.append(f"<h3>{label}</h3>" + "".join(f"<p>{e(t)}</p>" for t in texts))
            md.extend([f"### {label}", *texts])
        texts = list(
            dict.fromkeys(
                obj[key]
                for obj in walk(ad.get("creative", {}))
                for key in ("body", "message", "text", "title")
                if isinstance(obj.get(key), str)
            )
        )
        parts.append(
            "<details><summary>Dostępne teksty reklamy (oryginał)</summary>"
            + "".join(f"<pre>{e(t)}</pre>" for t in texts)
            + "</details></article>"
        )
    parts.append(
        "<footer><p>— oznacza brak raportowanej wartości lub brak podstaw do obliczenia. "
        "Źródło: Meta Marketing API; obliczenia Python; ocena materiałów i hipotezy: agent. "
        "Raport lokalny. Nie wprowadzono zmian w reklamach.</p></footer>"
    )
    md.append(
        "— oznacza brak raportowanej wartości lub brak podstaw do obliczenia. "
        "Źródło: Meta Marketing API; obliczenia Python; ocena materiałów i hipotezy: agent. "
        "Nie wprowadzono zmian w reklamach."
    )
    css = """body{margin:0;
background:#eef2f6;
color:#172c45;
font:17px/1.65 system-ui,sans-serif}

main{max-width:1120px;
margin:auto;
padding:32px 20px}
header,section,article,footer{background:white;
padding:36px;
margin-bottom:24px;
border-radius:12px}

h1{font-size:38px;
line-height:1.15}
h2{font-size:25px;
line-height:1.3}
h3{font-size:18px;
color:#0056a6}
.logo{width:175px;
height:auto}
.eyebrow{letter-spacing:2px;
font-size:12px;
color:#0060a9}

p{max-width:94ch}
.meta{font-size:13px;
color:#56677a;
overflow-wrap:anywhere}
.coverage{border-left:3px solid #00a1db;
padding-left:15px;
background:#f5faff}

.gallery{display:flex;
gap:12px;
overflow-x:auto;
padding:12px 0}
.gallery a{flex:0 0 245px;
background:#f2f5f8;
border-radius:8px;
display:flex;
align-items:center;
justify-content:center}
.gallery img{max-width:245px;
max-height:340px;
width:auto;
height:auto;
object-fit:contain}

dl{display:grid;
grid-template-columns:repeat(3,1fr);
gap:12px}
dl div{background:#f2f6fa;
padding:14px;
border-radius:6px}
dt{font-size:12px}
dd{margin:3px 0 0;
font-size:24px;
font-weight:650}
a{color:#005ba7}
nav a{display:inline-block;
padding:4px 10px}
pre{font:14px/1.6 system-ui;
white-space:pre-wrap;
background:#f5f7fa;
padding:16px;
overflow-wrap:anywhere}
details{margin-top:20px}
summary{cursor:pointer}

@media(max-width:650px){main{padding:8px}
header,section,article,footer{padding:20px}
h1{font-size:29px}
dl{grid-template-columns:repeat(2,1fr)}
}

@media print{body{background:white;
font-size:11pt}
main{padding:0}
article{break-before:page}
header,section,article{padding:12px}
.gallery{flex-wrap:wrap;
overflow:visible}
.gallery a{flex-basis:160px}
.gallery img{max-width:160px;
max-height:200px}
details,nav{display:none}
}
"""
    output = (
        '<!doctype html><html lang="pl"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + f"<title>{e(title)}</title><style>{css}</style><main>"
        + "".join(parts)
        + "</main></html>"
    )
    for name, body in [
        ("report.html", output),
        ("report.md", "\n\n".join(md) + "\n"),
        ("report-metrics.json", json.dumps(stats, ensure_ascii=False, indent=2)),
    ]:
        (p / name).write_text(body)
        (p / name).chmod(0o600)
    return {
        "html": str((p / "report.html").resolve()),
        "markdown": str((p / "report.md").resolve()),
        "cards": len(ids),
        "language_review": "required_after_render",
    }
