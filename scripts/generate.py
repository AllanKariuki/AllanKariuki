#!/usr/bin/env python3
"""Generate self-hosted SVG assets for the AllanKariuki profile README.

Stdlib-only (Python 3.11+). Run ``python scripts/generate.py`` with a GitHub
token in ``METRICS_TOKEN`` (or ``GITHUB_TOKEN``) to regenerate every asset, or
``python scripts/generate.py --offline-static`` to only (re)write the static
header / typing / footer SVGs without touching the network.

All SVGs are rendered into memory first and only written to ``assets/`` once
every fetch and render has succeeded, so a failure keeps the last good assets.
"""

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

GRAPHQL_URL = "https://api.github.com/graphql"
USER_AGENT = "AllanKariuki-profile-generator"

ACCENT = "#00ff41"
BG = "#0d1117"
TEXT = "#ffffff"
MUTED = "#8b949e"
GRID = "#21262d"
FONT = "'Segoe UI', Ubuntu, -apple-system, BlinkMacSystemFont, sans-serif"
MONO = "'Fira Code', 'Cascadia Code', Consolas, 'Courier New', monospace"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

PROFILE_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name color } }
        }
      }
    }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]
    ) { totalCount }
  }
}
"""

CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

TROPHY_THRESHOLDS = {
    "Commits": {"S": 2000, "A": 1000, "B": 500, "C": 100},
    "Stars": {"S": 100, "A": 50, "B": 20, "C": 5},
    "Followers": {"S": 100, "A": 50, "B": 20, "C": 10},
    "Repos": {"S": 80, "A": 50, "B": 30, "C": 10},
    "PRs": {"S": 200, "A": 100, "B": 50, "C": 10},
    "Issues": {"S": 100, "A": 50, "B": 20, "C": 5},
    "Years": {"S": 5, "A": 4, "B": 3, "C": 1},
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def esc(text):
    """XML-escape a string so it is safe inside SVG text/attributes."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def fmt_num(value):
    return f"{value:,}"


def fmt_day(d):
    return f"{MONTHS[d.month - 1]} {d.day}"


def fmt_range(start, end):
    """Format a date range like ``Nov 22 - Nov 25``; add years when needed."""
    if start is None or end is None:
        return "—"
    this_year = date.today().year
    if start == end:
        return fmt_day(start) if start.year == this_year else f"{fmt_day(start)}, {start.year}"
    if start.year == end.year:
        if start.year == this_year:
            return f"{fmt_day(start)} - {fmt_day(end)}"
        return f"{fmt_day(start)}, {start.year} - {fmt_day(end)}, {end.year}"
    return f"{fmt_day(start)}, {start.year} - {fmt_day(end)}, {end.year}"


def fmt_total_range(start):
    return f"{fmt_day(start)}, {start.year} - Present"


def nice_max(value):
    """Round a value up to a 'nice' axis maximum (1, 2, 4, 5, 8, 10, ...)."""
    if value <= 0:
        return 1
    mag = 10 ** math.floor(math.log10(value))
    for m in (1, 2, 4, 5, 8, 10):
        if value <= m * mag:
            return m * mag
    return 10 * mag


def catmull_rom_to_bezier(points, y_min=None, y_max=None):
    """Smooth a list of (x, y) points into a cubic-bezier SVG path string.

    When ``y_min``/``y_max`` are given, every control-point y is clamped into
    that range. A cubic Bezier stays inside the convex hull of its control
    points, so this guarantees the curve never overshoots past those bounds
    (e.g. it cannot dip below the zero baseline).
    """
    if len(points) < 2:
        return ""

    def at(i):
        if i < 0:
            return points[0]
        if i >= len(points):
            return points[-1]
        return points[i]

    def clamp_y(y):
        if y_min is not None:
            y = max(y, y_min)
        if y_max is not None:
            y = min(y, y_max)
        return y

    d = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0, p1, p2, p3 = at(i - 1), points[i], points[i + 1], at(i + 2)
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = clamp_y(p1[1] + (p2[1] - p0[1]) / 6.0)
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = clamp_y(p2[1] - (p3[1] - p1[1]) / 6.0)
        d.append(f"C {c1x:.1f} {c1y:.1f}, {c2x:.1f} {c2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d)


def _bg(width, height, rx=12):
    return f'<rect width="{width}" height="{height}" rx="{rx}" fill="{BG}"/>'


# --------------------------------------------------------------------------- #
# GitHub GraphQL
# --------------------------------------------------------------------------- #

def gql(token, query, variables):
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"bearer {token}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    if "errors" in body:
        messages = "; ".join(e.get("message", "?") for e in body["errors"])
        raise RuntimeError(f"GraphQL error: {messages}")
    return body.get("data")


def fetch_profile(token, user):
    repositories = []
    stars = 0
    languages = {}
    created_at = None
    followers = 0
    contributed_to = 0
    total_repos = 0
    after = None

    while True:
        data = gql(token, PROFILE_QUERY, {"login": user, "after": after})
        u = (data or {}).get("user")
        if u is None:
            raise RuntimeError(f"GitHub user {user!r} not found")
        if created_at is None:
            created_at = u["createdAt"]
            followers = u["followers"]["totalCount"]
            contributed_to = u["repositoriesContributedTo"]["totalCount"]
        repo = u["repositories"]
        total_repos = repo["totalCount"]
        for node in repo["nodes"]:
            repositories.append(node)
            stars += node["stargazerCount"]
            for edge in (node["languages"] or {}).get("edges", []):
                name = edge["node"]["name"]
                color = edge["node"]["color"] or "#8b949e"
                entry = languages.setdefault(name, {"color": color, "size": 0})
                entry["size"] += edge["size"]
        if not repo["pageInfo"]["hasNextPage"]:
            break
        after = repo["pageInfo"]["endCursor"]

    return {
        "created_at": created_at,
        "followers": followers,
        "repos": total_repos,
        "stars": stars,
        "contributed_to": contributed_to,
        "languages": languages,
    }


def fetch_contributions(token, user, created_at):
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    totals = {"commits": 0, "prs": 0, "issues": 0, "reviews": 0}
    calendar = {}

    for year in range(created.year, now.year + 1):
        start = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
        end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        if start > end:
            continue
        variables = {
            "login": user,
            "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data = gql(token, CONTRIB_QUERY, variables)
        collection = data["user"]["contributionsCollection"]
        totals["commits"] += collection["totalCommitContributions"]
        totals["prs"] += collection["totalPullRequestContributions"]
        totals["issues"] += collection["totalIssueContributions"]
        totals["reviews"] += collection["totalPullRequestReviewContributions"]
        for week in collection["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                calendar[day["date"]] = day["contributionCount"]

    return {"totals": totals, "calendar": calendar}


# --------------------------------------------------------------------------- #
# Derived metrics
# --------------------------------------------------------------------------- #

def compute_streaks(calendar, today=None):
    """Compute current/longest streaks from a ``{date: contributionCount}`` map.

    A day counts as active when ``contributionCount > 0``. Today is included in
    the current streak even when it has no contributions yet (the day is not
    over, so it does not break the streak).
    """
    today = today or date.today()
    active = set()
    for d, count in calendar.items():
        if count > 0:
            active.add(date.fromisoformat(d))

    def count_back(end):
        d = end
        while d in active:
            d -= timedelta(days=1)
        return d + timedelta(days=1)

    if today in active:
        current_start = count_back(today)
        current_end = today
    elif (today - timedelta(days=1)) in active:
        current_start = count_back(today - timedelta(days=1))
        current_end = today
    else:
        current_start = None
        current_end = None

    longest = 0
    longest_start = None
    longest_end = None
    run_start = None
    run_end = None
    for d in sorted(active):
        if run_start is None:
            run_start = run_end = d
        elif d == run_end + timedelta(days=1):
            run_end = d
        else:
            length = (run_end - run_start).days + 1
            if length > longest:
                longest, longest_start, longest_end = length, run_start, run_end
            run_start = run_end = d
    if run_start is not None:
        length = (run_end - run_start).days + 1
        if length > longest:
            longest, longest_start, longest_end = length, run_start, run_end

    total_start = min((date.fromisoformat(d) for d in calendar), default=today)

    return {
        "current_length": (current_end - current_start).days + 1 if current_start else 0,
        "current_start": current_start,
        "current_end": current_end,
        "longest_length": longest,
        "longest_start": longest_start,
        "longest_end": longest_end,
        "total_start": total_start,
        "total_contributions": sum(calendar.values()),
    }


# --------------------------------------------------------------------------- #
# SVG renderers
# --------------------------------------------------------------------------- #

def render_header():
    width, height = 720, 220
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Allan Kariuki banner">',
        "<defs>",
        '<linearGradient id="hg" x1="0" y1="0" x2="1" y2="0">',
        f'<stop offset="0" stop-color="{BG}"/>',
        f'<stop offset="1" stop-color="{ACCENT}"/>',
        "</linearGradient>",
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="url(#hg)"/>',
        f'<path d="M0 178 C 120 214, 240 120, 360 178 S 600 214, 720 178 '
        f'L 720 {height} L 0 {height} Z" fill="{BG}"/>',
        "<g>",
        '<animate attributeName="opacity" from="0" to="1" dur="1.2s" fill="freeze" begin="0s"/>',
        f'<text x="{width // 2}" y="88" text-anchor="middle" font-family="{FONT}" '
        f'font-size="64" font-weight="700" fill="{TEXT}">Allan Kariuki</text>',
        f'<text x="{width // 2}" y="132" text-anchor="middle" font-family="{FONT}" '
        f'font-size="18" fill="{TEXT}">{esc("Software Engineer | ML · Backend · Web3")}</text>',
        "</g>",
        "</svg>",
    ]
    return "\n".join(parts)


def render_typing():
    width, height = 720, 50
    lines = [
        "$ whoami",
        "> Software Engineer",
        "> ML Engineer",
        "> building for East Africa from Nairobi, Kenya",
    ]
    n = len(lines)
    per = 4.0
    total = n * per
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Terminal typing animation">',
        f'<rect width="{width}" height="{height}" rx="8" fill="{BG}"/>',
        "<style>",
        f".t {{ font-family: {MONO}; font-size: 20px; fill: {ACCENT}; }}",
        "@keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }",
        ".cursor { animation: blink 0.8s steps(1) infinite; }",
    ]
    for i in range(n):
        p0 = (i * per) / total * 100.0
        p1 = (i * per + 1.0) / total * 100.0
        p2 = (i * per + 3.0) / total * 100.0
        p3 = (i * per + 3.4) / total * 100.0
        hidden = "-webkit-clip-path: inset(0 100% 0 0); clip-path: inset(0 100% 0 0); opacity: 0"
        shown = "-webkit-clip-path: inset(0 0 0 0); clip-path: inset(0 0 0 0); opacity: 1"
        parts.append(f"@keyframes l{i} {{")
        parts.append(f"  0% {{ {hidden}; }}")
        if p0 > 0:
            parts.append(f"  {p0:.3f}% {{ {hidden}; }}")
        parts.append(f"  {p1:.3f}% {{ {shown}; }}")
        parts.append(f"  {p2:.3f}% {{ {shown}; }}")
        parts.append(f"  {p3:.3f}% {{ {hidden}; }}")
        parts.append(f"  100% {{ {hidden}; }}")
        parts.append("}")
        parts.append(f".l{i} {{ animation: l{i} {total}s linear infinite; }}")
    parts.append("</style>")
    for i, line in enumerate(lines):
        parts.append(
            f'<text class="t l{i}" x="{width // 2}" y="34" '
            f'text-anchor="middle">{esc(line)}<tspan class="cursor">▌</tspan></text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def render_footer():
    width, height = 720, 100
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Footer wave">',
        "<defs>",
        '<linearGradient id="fg" x1="0" y1="0" x2="1" y2="0">',
        f'<stop offset="0" stop-color="{ACCENT}"/>',
        f'<stop offset="1" stop-color="{BG}"/>',
        "</linearGradient>",
        "</defs>",
        f'<path d="M0 40 C 120 4, 240 76, 360 40 S 600 4, 720 40 '
        f'L 720 {height} L 0 {height} Z" fill="url(#fg)"/>',
        "</svg>",
    ]
    return "\n".join(parts)


def render_stats(d):
    width, height = 480, 220
    rows = [
        ("Stars", d["stars"]),
        ("Commits", d["commits"]),
        ("Pull Requests", d["prs"]),
        ("Issues", d["issues"]),
        ("Contributed To", d["contributed_to"]),
    ]
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub stats">',
        _bg(width, height),
        f'<text x="24" y="38" font-family="{FONT}" font-size="16" font-weight="700" '
        f'fill="{ACCENT}">{esc("Allan's GitHub Stats")}</text>',
    ]
    y = 74
    for label, value in rows:
        parts.append(
            f'<text x="24" y="{y}" font-family="{FONT}" font-size="13" '
            f'fill="{MUTED}">{esc(label)}</text>'
        )
        parts.append(
            f'<text x="{width - 24}" y="{y}" text-anchor="end" font-family="{FONT}" '
            f'font-size="15" font-weight="700" fill="{TEXT}">{fmt_num(value)}</text>'
        )
        y += 26
    parts.append("</svg>")
    return "\n".join(parts)


def render_langs(d):
    width, height = 480, 220
    langs = list(d["languages"])[:9]  # top 8 + optional "Other"
    total = sum(lang["size"] for lang in langs) or 1
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Top languages">',
        _bg(width, height),
        f'<text x="24" y="38" font-family="{FONT}" font-size="16" font-weight="700" '
        f'fill="{ACCENT}">Top Languages</text>',
    ]
    if not langs:
        parts.append(
            f'<text x="24" y="100" font-family="{FONT}" font-size="13" '
            f'fill="{MUTED}">No languages yet</text>'
        )
    else:
        bar_x, bar_y, bar_w, bar_h = 24, 60, width - 48, 12
        x = float(bar_x)
        for lang in langs:
            seg_w = (lang["size"] / total) * bar_w
            parts.append(
                f'<rect x="{x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" '
                f'fill="{esc(lang["color"])}"/>'
            )
            x += seg_w
        col_x = [24, 250]
        for idx, lang in enumerate(langs):
            cx = col_x[idx % 2]
            cy = 108 + (idx // 2) * 24
            pct = lang["size"] / total * 100.0
            parts.append(
                f'<rect x="{cx}" y="{cy - 9}" width="10" height="10" rx="2" '
                f'fill="{esc(lang["color"])}"/>'
            )
            parts.append(
                f'<text x="{cx + 16}" y="{cy}" font-family="{FONT}" font-size="12" '
                f'fill="{TEXT}">{esc(lang["name"])}</text>'
            )
            parts.append(
                f'<text x="{cx + 206}" y="{cy}" text-anchor="end" font-family="{FONT}" '
                f'font-size="12" fill="{MUTED}">{pct:.1f}%</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def render_streak(d):
    width, height = 480, 160
    s = d["streak"]
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Contribution streaks">',
        _bg(width, height),
    ]
    columns = [
        ("Total Contributions", 80, fmt_num(s["total_contributions"]),
         fmt_total_range(s["total_start"]), False),
        ("Current Streak", 240, fmt_num(s["current_length"]),
         fmt_range(s["current_start"], s["current_end"]), True),
        ("Longest Streak", 400, fmt_num(s["longest_length"]),
         fmt_range(s["longest_start"], s["longest_end"]), False),
    ]
    for label, cx, _value, _range, _ring in columns:
        parts.append(
            f'<text x="{cx}" y="42" text-anchor="middle" font-family="{FONT}" '
            f'font-size="11" fill="{MUTED}">{esc(label)}</text>'
        )
    # Total
    parts.append(
        f'<text x="80" y="92" text-anchor="middle" font-family="{FONT}" font-size="28" '
        f'font-weight="700" fill="{TEXT}">{fmt_num(s["total_contributions"])}</text>'
    )
    # Current (inside a ring)
    parts.append(f'<circle cx="240" cy="88" r="36" fill="none" stroke="{ACCENT}" stroke-width="2"/>')
    parts.append(
        f'<text x="240" y="95" text-anchor="middle" font-family="{FONT}" font-size="24" '
        f'font-weight="700" fill="{TEXT}">{fmt_num(s["current_length"])}</text>'
    )
    # Longest
    parts.append(
        f'<text x="400" y="92" text-anchor="middle" font-family="{FONT}" font-size="28" '
        f'font-weight="700" fill="{TEXT}">{fmt_num(s["longest_length"])}</text>'
    )
    parts.append(
        f'<text x="80" y="124" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'fill="{MUTED}">{esc(fmt_total_range(s["total_start"]))}</text>'
    )
    parts.append(
        f'<text x="240" y="136" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'fill="{MUTED}">{esc(fmt_range(s["current_start"], s["current_end"]))}</text>'
    )
    parts.append(
        f'<text x="400" y="124" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'fill="{MUTED}">{esc(fmt_range(s["longest_start"], s["longest_end"]))}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def render_activity(d):
    width, height = 720, 240
    days = d["activity"]
    n = len(days)
    ml, mr, mt, mb = 44, 18, 40, 30
    px0, px1 = ml, width - mr
    py0, py1 = mt, height - mb
    pw, ph = px1 - px0, py1 - py0
    counts = [day["count"] for day in days]
    ymax = nice_max(max(counts) if counts else 0)

    points = []
    for i, count in enumerate(counts):
        x = px0 + (pw * i / (n - 1)) if n > 1 else px0
        y = py1 - (count / ymax) * ph
        points.append((x, y))

    line_d = catmull_rom_to_bezier(points, py0, py1)
    area_d = f"{line_d} L {px1} {py1} L {px0} {py1} Z"

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Contribution graph">',
        _bg(width, height),
        f'<text x="{px0}" y="26" font-family="{FONT}" font-size="14" font-weight="700" '
        f'fill="{TEXT}">{esc("Allan Kariuki's Contribution Graph")}</text>',
        "<defs>",
        '<linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">',
        f'<stop offset="0" stop-color="{ACCENT}" stop-opacity="0.25"/>',
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/>',
        "</linearGradient>",
        f'<clipPath id="pc"><rect x="{px0 - 4}" y="{py0 - 4}" '
        f'width="{pw + 8}" height="{ph + 8}"/></clipPath>',
        "</defs>",
    ]

    for frac in (0.0, 0.5, 1.0):
        val = ymax * frac
        gy = py1 - frac * ph
        parts.append(
            f'<line x1="{px0}" y1="{gy:.1f}" x2="{px1}" y2="{gy:.1f}" '
            f'stroke="{GRID}" stroke-dasharray="3 3"/>'
        )
        label = str(int(val)) if val == int(val) else f"{val:g}"
        parts.append(
            f'<text x="{px0 - 8}" y="{gy + 4:.1f}" text-anchor="end" font-family="{FONT}" '
            f'font-size="10" fill="{MUTED}">{esc(label)}</text>'
        )

    parts.append(f'<path d="{area_d}" fill="url(#ag)" clip-path="url(#pc)"/>')
    parts.append(f'<path d="{line_d}" fill="none" stroke="{ACCENT}" stroke-width="2" clip-path="url(#pc)"/>')
    for x, y in points:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{TEXT}"/>')
    for i in range(0, n, 5):
        x = points[i][0]
        day = days[i]["date"]
        parts.append(
            f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="10" fill="{MUTED}">{day.day}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _rank(value, thresholds):
    for rank in ("S", "A", "B", "C"):
        if value >= thresholds[rank]:
            return rank
    return "?"


def _cup(cx, top):
    w = 20
    parts = [
        f'<path d="M {cx - w} {top} L {cx + w} {top} L {cx + w} {top + 16} '
        f'Q {cx + w} {top + 22} {cx + w - 6} {top + 22} '
        f'L {cx + 5} {top + 22} L {cx + 5} {top + 28} L {cx - 5} {top + 28} '
        f'L {cx - 5} {top + 22} L {cx - w + 6} {top + 22} '
        f'Q {cx - w} {top + 22} {cx - w} {top + 16} Z" '
        f'fill="none" stroke="{ACCENT}" stroke-width="2"/>',
        f'<path d="M {cx - w} {top + 3} Q {cx - w - 7} {top + 3} {cx - w - 7} {top + 9} '
        f'Q {cx - w - 7} {top + 15} {cx - w} {top + 15}" '
        f'fill="none" stroke="{ACCENT}" stroke-width="2"/>',
        f'<path d="M {cx + w} {top + 3} Q {cx + w + 7} {top + 3} {cx + w + 7} {top + 9} '
        f'Q {cx + w + 7} {top + 15} {cx + w} {top + 15}" '
        f'fill="none" stroke="{ACCENT}" stroke-width="2"/>',
        f'<rect x="{cx - 14}" y="{top + 28}" width="28" height="6" rx="2" '
        f'fill="none" stroke="{ACCENT}" stroke-width="2"/>',
    ]
    return "".join(parts)


def render_trophies(d):
    width, height = 800, 140
    items = [
        ("Commits", d["commits"]),
        ("Stars", d["stars"]),
        ("Followers", d["followers"]),
        ("Repos", d["repos"]),
        ("PRs", d["prs"]),
        ("Issues", d["issues"]),
        ("Years", d["years"]),
    ]
    col_w = width / len(items)
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub trophies">',
        _bg(width, height),
    ]
    for i, (label, value) in enumerate(items):
        cx = col_w * (i + 0.5)
        rank = _rank(value, TROPHY_THRESHOLDS[label])
        parts.append(
            f'<text x="{cx:.1f}" y="22" text-anchor="middle" font-family="{FONT}" '
            f'font-size="15" font-weight="700" fill="{ACCENT}">{rank}</text>'
        )
        parts.append(_cup(cx, 30))
        parts.append(
            f'<text x="{cx:.1f}" y="104" text-anchor="middle" font-family="{FONT}" '
            f'font-size="11" fill="{MUTED}">{esc(label)}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="117" text-anchor="middle" font-family="{FONT}" '
            f'font-size="12" font-weight="700" fill="{TEXT}">{fmt_num(value)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate profile SVG assets.")
    parser.add_argument(
        "--offline-static",
        action="store_true",
        help="Only write header/typing/footer SVGs (no GitHub token required).",
    )
    args = parser.parse_args(argv)

    out_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    )
    os.makedirs(out_dir, exist_ok=True)

    rendered = {
        "header.svg": render_header(),
        "typing.svg": render_typing(),
        "footer.svg": render_footer(),
    }

    if not args.offline_static:
        token = os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN")
        user = os.environ.get("GH_USER", "AllanKariuki")
        if not token:
            print("error: no GitHub token (set METRICS_TOKEN or GITHUB_TOKEN)", file=sys.stderr)
            return 1
        try:
            profile = fetch_profile(token, user)
            contrib = fetch_contributions(token, user, profile["created_at"])
            calendar = contrib["calendar"]
            totals = contrib["totals"]
            streaks = compute_streaks(calendar)

            created = datetime.fromisoformat(profile["created_at"].replace("Z", "+00:00")).date()
            years = date.today().year - created.year

            langs_sorted = sorted(
                profile["languages"].items(), key=lambda kv: -kv[1]["size"]
            )
            total_bytes = sum(v["size"] for _, v in langs_sorted)
            lang_list = [
                {"name": name, "color": c["color"], "size": c["size"]}
                for name, c in langs_sorted[:8]
            ]
            shown_bytes = sum(lang["size"] for lang in lang_list)
            if total_bytes > shown_bytes:
                lang_list.append({"name": "Other", "color": "#8b949e", "size": total_bytes - shown_bytes})

            today = date.today()
            activity = []
            for i in range(30, -1, -1):
                day = today - timedelta(days=i)
                activity.append({"date": day, "count": calendar.get(day.isoformat(), 0)})

            data = {
                "stars": profile["stars"],
                "commits": totals["commits"],
                "prs": totals["prs"],
                "issues": totals["issues"],
                "contributed_to": profile["contributed_to"],
                "followers": profile["followers"],
                "repos": profile["repos"],
                "years": years,
                "languages": lang_list,
                "streak": streaks,
                "activity": activity,
            }
            rendered.update({
                "stats.svg": render_stats(data),
                "top-langs.svg": render_langs(data),
                "streak.svg": render_streak(data),
                "activity.svg": render_activity(data),
                "trophies.svg": render_trophies(data),
            })
        except Exception as exc:  # keep last good assets on failure
            print(f"error: {exc}", file=sys.stderr)
            return 1

    for name, svg in rendered.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            handle.write(svg)

    print(f"wrote {len(rendered)} SVG file(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
