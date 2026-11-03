"""Génère dist/contribs.svg : une grille de contributions par année
depuis la création du compte, + total, plus longue série et série actuelle.
Utilise uniquement la bibliothèque standard et l'API GraphQL de GitHub."""
import datetime as dt
import json
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "ValentinLallement")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/contribs.svg"

GREEN, PINK, BG, BORDER = "#00FF99", "#FF0066", "#0b0f17", "#1f2937"
TXT, MUTED = "#f3f4f6", "#6b7280"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MOIS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"Erreur GraphQL : {data['errors']}")
    return data["data"]


def fetch():
    created = gql("query($u:String!){user(login:$u){createdAt}}", {"u": USER})["user"]["createdAt"]
    first_year = int(created[:4])
    today = dt.date.today()
    q = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
      contributionsCollection(from:$f,to:$t){contributionCalendar{
        weeks{contributionDays{date contributionCount}}}}}}"""
    days = {}
    for y in range(first_year, today.year + 1):
        cal = gql(q, {"u": USER, "f": f"{y}-01-01T00:00:00Z", "t": f"{y}-12-31T23:59:59Z"})
        for w in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return days, first_year, today


def streaks(days, today):
    longest = run = 0
    d = min(dt.date.fromisoformat(k) for k in days)
    while d <= today:
        if days.get(d.isoformat(), 0) > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
        d += dt.timedelta(days=1)
    # série actuelle : on tolère que la journée d'aujourd'hui soit encore vide
    cur, d = 0, today
    if days.get(d.isoformat(), 0) == 0:
        d -= dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    return longest, cur


def level(n, mx):
    if n == 0:
        return 0
    return min(4, 1 + int(3 * n / max(mx, 1)))


def render(days, first_year, today):
    total = sum(days.values())
    longest, cur = streaks(days, today)
    mx = max(days.values() or [1])
    years = list(range(today.year, first_year - 1, -1))  # plus récent en haut

    W, cell, gap = 1000, 12, 3
    left, top = 135, 150
    row_h = 7 * (cell + gap) + 28
    H = top + row_h * len(years) + 20

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         "<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
         ".c{animation:pop .5s ease-out both}@keyframes pop{from{opacity:0}to{opacity:1}}"
         "</style>",
         f'<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>',
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="17.5" fill="none" stroke="{BORDER}"/>']

    # Chiffres clés
    stats = [(f"{total}", "contributions au total", GREEN),
             (f"{longest} j", "plus longue série", PINK),
             (f"{cur} j", "série actuelle", TXT)]
    for i, (val, lab, col) in enumerate(stats):
        x = 40 + i * 320
        o.append(f'<text x="{x}" y="70" font-size="34" font-weight="700" fill="{col}">{val}</text>')
        o.append(f'<text x="{x}" y="96" font-size="13" fill="{MUTED}">{lab}</text>')
    o.append(f'<text x="40" y="128" font-size="12" fill="{MUTED}">depuis {first_year} · mis à jour le {today.strftime("%d/%m/%Y")}</text>')

    # Une grille par année
    for r, y in enumerate(years):
        y0 = top + r * row_h
        ytot = sum(v for k, v in days.items() if k.startswith(str(y)))
        o.append(f'<text x="40" y="{y0 + 50}" font-size="20" font-weight="700" fill="{TXT}">{y}</text>')
        o.append(f'<text x="40" y="{y0 + 70}" font-size="11" fill="{MUTED}">{ytot} contrib.</text>')
        jan1 = dt.date(y, 1, 1)
        start = jan1 - dt.timedelta(days=(jan1.weekday() + 1) % 7)  # dimanche
        d = jan1
        last = min(dt.date(y, 12, 31), today)
        while d <= dt.date(y, 12, 31):
            wk = (d - start).days // 7
            dow = (d.weekday() + 1) % 7
            x = left + wk * (cell + gap)
            yy = y0 + 10 + dow * (cell + gap)
            if d.day == 1 and dow < 7:
                o.append(f'<text x="{x}" y="{y0 + 4}" font-size="10" fill="{MUTED}">{MOIS[d.month-1]}</text>')
            if d <= last:
                lv = level(days.get(d.isoformat(), 0), mx)
                delay = round(0.004 * wk + 0.15 * r, 3)
                o.append(f'<rect class="c" style="animation-delay:{delay}s" x="{x}" y="{yy}" '
                         f'width="{cell}" height="{cell}" rx="2.5" fill="{LEVELS[lv]}"/>')
            else:
                o.append(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="2.5" '
                         f'fill="none" stroke="{BORDER}"/>')
            d += dt.timedelta(days=1)

    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    if os.environ.get("DEMO"):
        import random
        random.seed(1)
        today = dt.date(2026, 11, 3)
        days, d = {}, dt.date(2024, 6, 1)
        while d <= today:
            days[d.isoformat()] = random.choice([0, 0, 0, 1, 2, 3, 5, 8])
            d += dt.timedelta(days=1)
        first_year = 2024
    else:
        days, first_year, today = fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(days, first_year, today))
    print(f"OK : {OUT}")
