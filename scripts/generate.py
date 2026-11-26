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

ACCENT = "#58a6ff"
ACCENT_SOFT = "#1f6feb"
BG = "#0d1117"
TEXT = "#ffffff"
MUTED = "#8b949e"
GRID = "#21262d"
FONT = "'Segoe UI', Ubuntu, -apple-system, BlinkMacSystemFont, sans-serif"
MONO = "'Fira Code', 'Cascadia Code', Consolas, 'Courier New', monospace"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# GitHub Octicons 16px path data (viewBox "0 0 16 16").
# (c) GitHub, MIT License — https://github.com/primer/octicons (MIT).
OCTICONS = {
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z",
    "git-commit": "M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z",
    "git-pull-request": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z",
    "flame": "M9.533.753V.752c.217 2.385 1.463 3.626 2.653 4.81C13.37 6.74 14.498 7.863 14.498 10c0 3.5-3 6-6.5 6S1.5 13.512 1.5 10c0-1.298.536-2.56 1.425-3.286.376-.308.862 0 1.035.454C4.46 8.487 5.581 8.419 6 8c.282-.282.341-.811-.003-1.5C4.34 3.187 7.035.75 8.77.146c.39-.137.726.194.763.607ZM7.998 14.5c2.832 0 5-1.98 5-4.5 0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432.696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.545.84-2.403.633a2.79 2.79 0 0 1-1.436-.874A3.198 3.198 0 0 0 3 10c0 2.53 2.164 4.5 4.998 4.5Z",
    "pulse": "M6 2c.306 0 .582.187.696.471L10 10.731l1.304-3.26A.751.751 0 0 1 12 7h3.25a.75.75 0 0 1 0 1.5h-2.742l-1.812 4.528a.751.751 0 0 1-1.392 0L6 4.77 4.696 8.03A.75.75 0 0 1 4 8.5H.75a.75.75 0 0 1 0-1.5h2.742l1.812-4.529A.751.751 0 0 1 6 2Z",
    "clock": "M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm7-3.25v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5a.75.75 0 0 1 1.5 0Z",
    "trophy": "M3.217 6.962A3.75 3.75 0 0 1 0 3.25v-.5C0 1.784.784 1 1.75 1h1.356c.228-.585.796-1 1.462-1h6.864c.647 0 1.227.397 1.462 1h1.356c.966 0 1.75.784 1.75 1.75v.5a3.75 3.75 0 0 1-3.217 3.712 5.014 5.014 0 0 1-2.771 3.117l.144 1.446c.005.05.03.12.114.204.086.087.217.17.373.227.283.103.618.274.89.568.285.31.467.723.467 1.226v.75h1.25a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1 0-1.5H4v-.75c0-.503.182-.916.468-1.226.27-.294.606-.465.889-.568.139-.048.266-.126.373-.227.084-.085.109-.153.114-.204l.144-1.446a5.015 5.015 0 0 1-2.77-3.117ZM4.5 1.568V5.5a3.5 3.5 0 1 0 7 0V1.568a.068.068 0 0 0-.068-.068H4.568a.068.068 0 0 0-.068.068Zm2.957 8.902-.12 1.204c-.093.925-.858 1.47-1.467 1.691a.766.766 0 0 0-.3.176c-.037.04-.07.093-.07.21v.75h5v-.75c0-.117-.033-.17-.07-.21a.766.766 0 0 0-.3-.176c-.609-.221-1.374-.766-1.466-1.69l-.12-1.204a5.064 5.064 0 0 1-1.087 0ZM13 2.5v2.872a2.25 2.25 0 0 0 1.5-2.122v-.5a.25.25 0 0 0-.25-.25H13Zm-10 0H1.75a.25.25 0 0 0-.25.25v.5c0 .98.626 1.813 1.5 2.122Z",
    "graph": "M1.5 1.75V13.5h13.75a.75.75 0 0 1 0 1.5H.75a.75.75 0 0 1-.75-.75V1.75a.75.75 0 0 1 1.5 0Zm14.28 2.53-5.25 5.25a.75.75 0 0 1-1.06 0L7 7.06 4.28 9.78a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l3.25-3.25a.75.75 0 0 1 1.06 0L10 7.94l4.72-4.72a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Z",
}

# Classic github-readme-streak-stats fire glyph (24x24 viewBox).
FIRE_PATH = (
    "M12 1.5C12 1.5 13.8 4.6 13.8 7.1 13.8 8.9 12.6 10.2 11 10.2 9.4 10.2 8.2 8.9 8.2 7.1L8.2 6.8"
    "C6.6 8.7 5.6 11.2 5.6 13.9 5.6 17.5 8.5 20.4 12 20.4 15.5 20.4 18.4 17.5 18.4 13.9 18.4 9.1 16.1 4.8 12 1.5"
    "ZM11.7 17.6C10.3 17.6 9.2 16.5 9.2 15.1 9.2 13.8 10 12.9 11.4 12.6 12.8 12.3 14.3 11.6 15.1 10.5 15.4 11.6 15.6 12.7 15.6 13.8 15.6 15.9 13.9 17.6 11.7 17.6Z"
)

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
    yearly = {}
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
        yearly[year] = {
            "commits": collection["totalCommitContributions"],
            "prs": collection["totalPullRequestContributions"],
            "issues": collection["totalIssueContributions"],
            "reviews": collection["totalPullRequestReviewContributions"],
            "contributions": collection["contributionCalendar"]["totalContributions"],
        }
        for week in collection["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                calendar[day["date"]] = day["contributionCount"]

    return {"totals": totals, "yearly": yearly, "calendar": calendar}


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


def compute_grade(metrics):
    """Return an activity grade ``(letter, score)`` for a profile.

    The score (0-100) is a weighted sum of exponential CDFs ``1 - exp(-v/t)``,
    so each metric saturates towards its weight as its value grows. ``metrics``
    is a dict with keys: ``commits_this_year``, ``contributions_this_year``,
    ``prs``, ``current_streak``, ``weekly``, ``stars``, ``followers`` and
    ``contributed_to``.
    """
    terms = [
        ("commits_this_year", 25, 600),
        ("contributions_this_year", 25, 900),
        ("prs", 15, 80),
        ("current_streak", 10, 14),
        ("weekly", 10, 40),
        ("stars", 5, 30),
        ("followers", 5, 30),
        ("contributed_to", 5, 15),
    ]
    score = 0.0
    for key, weight, tau in terms:
        value = metrics.get(key, 0) or 0
        score += weight * (1.0 - math.exp(-value / tau))
    score = int(round(min(100.0, score)))
    if score >= 85:
        letter = "A+"
    elif score >= 75:
        letter = "A"
    elif score >= 65:
        letter = "A-"
    elif score >= 55:
        letter = "B+"
    elif score >= 45:
        letter = "B"
    elif score >= 35:
        letter = "B-"
    elif score >= 25:
        letter = "C+"
    else:
        letter = "C"
    return letter, score


def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_in_year(year):
    return 366 if _is_leap(year) else 365


def _month_length(year, month):
    """Length in days of ``month`` (1-12) in ``year``."""
    if month == 12:
        return (date(year + 1, 1, 1) - date(year, 12, 1)).days
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def weekly_series(calendar, year):
    """Sum daily contributions into 7-day buckets starting Jan 1 of ``year``.

    Returns a list of ``ceil(days_in_year / 7)`` weekly totals (the last bucket
    may be shorter than 7 days).
    """
    days_in_year = _days_in_year(year)
    buckets = [0] * ((days_in_year + 6) // 7)
    start = date(year, 1, 1)
    for day_str, count in calendar.items():
        day = date.fromisoformat(day_str)
        if day.year == year:
            doy = (day - start).days
            if 0 <= doy < days_in_year:
                buckets[doy // 7] += count
    return buckets


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
    width, height = 495, 195
    year = date.today().year
    rows = [
        ("star", "Total Stars Earned", fmt_num(d["stars"])),
        ("git-commit", f"Total Commits ({year})", fmt_num(d["commits_this_year"])),
        ("git-pull-request", "Pull Requests", fmt_num(d["prs"])),
        ("flame", "Current Streak", f'{d["streak"]["current_length"]} days'),
        ("pulse", "Weekly Trend", f'{d["weekly"]} this week'),
        ("clock", "Avg Contributions / Day", f'{d["avg_per_day"]:.1f}'),
        ("trophy", "Activity Grade", d["grade_letter"]),
        ("graph", "Contributions This Year", fmt_num(d["contributions_this_year"])),
    ]
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub stats">',
        f'<rect width="{width}" height="{height}" rx="12" fill="{BG}" '
        'stroke="#30363d" stroke-width="1"/>',
        f'<text x="24" y="38" font-family="{FONT}" font-size="18" font-weight="700" '
        f'fill="{ACCENT}">{esc("Allan's GitHub Stats")}</text>',
    ]
    icon_scale = 14 / 16
    y = 66
    for icon, label, value in rows:
        parts.append(
            f'<path d="{OCTICONS[icon]}" fill="{ACCENT}" '
            f'transform="translate(24, {y - 10.5}) scale({icon_scale})"/>'
        )
        parts.append(
            f'<text x="48" y="{y}" font-family="{FONT}" font-size="12.5" '
            f'fill="#c9d1d9">{esc(label)}</text>'
        )
        parts.append(
            f'<text x="330" y="{y}" text-anchor="end" font-family="{FONT}" '
            f'font-size="12.5" font-weight="700" fill="{TEXT}">{esc(value)}</text>'
        )
        y += 15.5
    # Activity grade ring
    cx, cy, r = 420, 105, 40
    circ = 2 * math.pi * r
    dash = circ * (d["grade_score"] / 100.0)
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#30363d" stroke-width="6"/>')
    if d["grade_score"] > 0:
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ACCENT}" '
            f'stroke-width="6" stroke-linecap="round" '
            f'stroke-dasharray="{dash:.2f} {circ:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
    parts.append(
        f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="24" font-weight="700" fill="{ACCENT}">{esc(d["grade_letter"])}</text>'
    )
    parts.append(
        f'<text x="{cx}" y="{cy + 28}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="12" fill="{MUTED}">{d["grade_score"]}%</text>'
    )
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
    width, height = 495, 195
    s = d["streak"]
    cx_left, cx_mid, cx_right = 82.5, 247.5, 412.5
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Contribution streaks">',
        _bg(width, height),
    ]
    for dx in (165, 330):
        parts.append(
            f'<line x1="{dx}" y1="28" x2="{dx}" y2="170" '
            f'stroke="{ACCENT}" stroke-width="1"/>'
        )
    # Left column: total contributions
    parts.append(
        f'<text x="{cx_left}" y="80" text-anchor="middle" font-family="{FONT}" '
        f'font-size="28" font-weight="700" fill="{TEXT}">{fmt_num(s["total_contributions"])}</text>'
    )
    parts.append(
        f'<text x="{cx_left}" y="134" text-anchor="middle" font-family="{FONT}" '
        f'font-size="14" fill="{TEXT}">Total Contributions</text>'
    )
    parts.append(
        f'<text x="{cx_left}" y="158" text-anchor="middle" font-family="{FONT}" '
        f'font-size="12" fill="{MUTED}">{esc(fmt_total_range(s["total_start"]))}</text>'
    )
    # Right column: longest streak
    parts.append(
        f'<text x="{cx_right}" y="80" text-anchor="middle" font-family="{FONT}" '
        f'font-size="28" font-weight="700" fill="{TEXT}">{fmt_num(s["longest_length"])}</text>'
    )
    parts.append(
        f'<text x="{cx_right}" y="134" text-anchor="middle" font-family="{FONT}" '
        f'font-size="14" fill="{TEXT}">Longest Streak</text>'
    )
    parts.append(
        f'<text x="{cx_right}" y="158" text-anchor="middle" font-family="{FONT}" '
        f'font-size="12" fill="{MUTED}">{esc(fmt_range(s["longest_start"], s["longest_end"]))}</text>'
    )
    # Middle column: ring with the streak-stats fire on top, current streak.
    ring_cy, ring_r = 78, 34
    parts.append(
        f'<circle cx="{cx_mid}" cy="{ring_cy}" r="{ring_r}" fill="none" '
        f'stroke="{ACCENT}" stroke-width="5"/>'
    )
    # Mask a bg-coloured gap in the ring top, then draw the fire.
    parts.append(f'<circle cx="{cx_mid}" cy="{ring_cy - ring_r}" r="14" fill="{BG}"/>')
    fire_scale = 1.2
    fire_cx, fire_cy = cx_mid, ring_cy - ring_r
    fire_tx = fire_cx - fire_scale * 12.0
    fire_ty = fire_cy - fire_scale * 10.95
    parts.append(
        f'<path d="{FIRE_PATH}" fill="{ACCENT}" '
        f'transform="translate({fire_tx:.2f} {fire_ty:.2f}) scale({fire_scale})"/>'
    )
    parts.append(
        f'<text x="{cx_mid}" y="{ring_cy + 8}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="24" font-weight="700" fill="{TEXT}">{fmt_num(s["current_length"])}</text>'
    )
    parts.append(
        f'<text x="{cx_mid}" y="134" text-anchor="middle" font-family="{FONT}" '
        f'font-size="14" font-weight="700" fill="{ACCENT}">Current Streak</text>'
    )
    parts.append(
        f'<text x="{cx_mid}" y="158" text-anchor="middle" font-family="{FONT}" '
        f'font-size="12" fill="{MUTED}">{esc(fmt_range(s["current_start"], s["current_end"]))}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def render_activity(d):
    width, height = 830, 260
    act = d["activity"]
    year = act["year"]
    today_doy = act["today_doy"]
    current = act["current"]
    previous = act["previous"]

    days_in_year = _days_in_year(year)
    n_buckets = len(current)
    today_bucket = min(today_doy // 7, n_buckets - 1)

    ml, mr, mt, mb = 48, 20, 56, 40
    px0, px1 = ml, width - mr
    py0, py1 = mt, height - mb
    pw, ph = px1 - px0, py1 - py0

    all_vals = list(current) + list(previous)
    ymax = nice_max(max(all_vals) if all_vals else 0)

    def x_for_bucket(i, days):
        start = i * 7
        end = min((i + 1) * 7, days)
        mid = (start + end) / 2.0
        return px0 + (mid / days) * pw

    # Current year: buckets up to and including today's bucket.
    cur_pts = []
    for i in range(today_bucket + 1):
        cur_pts.append((x_for_bucket(i, days_in_year), py1 - (current[i] / ymax) * ph))

    # Previous year: the whole year.
    prev_days = _days_in_year(year - 1)
    prev_pts = []
    for i in range(len(previous)):
        prev_pts.append((x_for_bucket(i, prev_days), py1 - (previous[i] / ymax) * ph))

    cur_line = catmull_rom_to_bezier(cur_pts, py0, py1) if len(cur_pts) >= 2 else ""
    cur_area = f"{cur_line} L {cur_pts[-1][0]:.1f} {py1} L {cur_pts[0][0]:.1f} {py1} Z" if cur_line else ""
    prev_line = catmull_rom_to_bezier(prev_pts, py0, py1) if len(prev_pts) >= 2 else ""

    # Ghost: from today's point, continue with last year's values for future weeks.
    ghost_pts = []
    if cur_pts and today_bucket < n_buckets - 1:
        ghost_pts.append(cur_pts[-1])
        for i in range(today_bucket + 1, n_buckets):
            value = previous[i] if i < len(previous) else 0
            ghost_pts.append((x_for_bucket(i, days_in_year), py1 - (value / ymax) * ph))
    ghost_line = catmull_rom_to_bezier(ghost_pts, py0, py1) if len(ghost_pts) >= 2 else ""
    ghost_area = f"{ghost_line} L {ghost_pts[-1][0]:.1f} {py1} L {ghost_pts[0][0]:.1f} {py1} Z" if ghost_line else ""

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Contribution activity">',
        _bg(width, height),
        f'<text x="24" y="30" font-family="{FONT}" font-size="14" font-weight="700" '
        f'fill="{ACCENT}">Contribution Activity · {year}</text>',
        # Legend (top-right).
        f'<line x1="590" y1="22" x2="612" y2="22" stroke="{ACCENT}" stroke-width="2.5"/>',
        f'<text x="618" y="26" font-family="{FONT}" font-size="11" fill="{MUTED}">This year</text>',
        f'<line x1="700" y1="22" x2="722" y2="22" stroke="{MUTED}" stroke-width="1.5" '
        'stroke-dasharray="1.5 4" stroke-linecap="round"/>',
        f'<text x="728" y="26" font-family="{FONT}" font-size="11" fill="{MUTED}">Last year</text>',
        "<defs>",
        f'<linearGradient id="linegrad" gradientUnits="userSpaceOnUse" '
        f'x1="{px0}" y1="0" x2="{px1}" y2="0">',
        '<stop offset="0" stop-color="#39d0d8"/>',
        f'<stop offset="0.33" stop-color="{ACCENT}"/>',
        '<stop offset="0.66" stop-color="#a371f7"/>',
        '<stop offset="1" stop-color="#bc8cff"/>',
        "</linearGradient>",
        '<linearGradient id="fademask" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0" stop-color="#ffffff"/>',
        '<stop offset="1" stop-color="#000000"/>',
        "</linearGradient>",
        f'<mask id="areamask"><rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" '
        'fill="url(#fademask)"/></mask>',
        f'<clipPath id="pc"><rect x="{px0}" y="{py0}" width="{pw}" height="{ph}"/></clipPath>',
        "</defs>",
    ]

    # Month gridlines + labels.
    for m in range(1, 13):
        start_doy = (date(year, m, 1) - date(year, 1, 1)).days
        gx = px0 + (start_doy / days_in_year) * pw
        parts.append(
            f'<line x1="{gx:.1f}" y1="{py0}" x2="{gx:.1f}" y2="{py1}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        mid_doy = start_doy + _month_length(year, m) / 2.0
        lx = px0 + (mid_doy / days_in_year) * pw
        parts.append(
            f'<text x="{lx:.1f}" y="{height - 14}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="11" fill="{MUTED}">{MONTHS[m - 1]}</text>'
        )

    # 4 horizontal gridlines.
    for frac in (0.0, 1 / 3, 2 / 3, 1.0):
        gy = py1 - frac * ph
        parts.append(
            f'<line x1="{px0}" y1="{gy:.1f}" x2="{px1}" y2="{gy:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )

    # Small max label top-left of the plot.
    parts.append(
        f'<text x="{px0}" y="{py0 - 8}" font-family="{FONT}" font-size="10" '
        f'fill="{MUTED}">{ymax:g}</text>'
    )

    # Previous-year full dotted line (behind everything else).
    if prev_line:
        parts.append(
            f'<path d="{prev_line}" fill="none" stroke="{MUTED}" stroke-width="1.5" '
            'stroke-dasharray="1.5 4" stroke-linecap="round" clip-path="url(#pc)"/>'
        )

    # Ghost (future) continuation in last year's values.
    if ghost_line:
        parts.append(f'<path d="{ghost_area}" fill="{ACCENT}" opacity="0.05" clip-path="url(#pc)"/>')
        parts.append(
            f'<path d="{ghost_line}" fill="none" stroke="{ACCENT}" stroke-width="2.5" '
            'opacity="0.25" clip-path="url(#pc)"/>'
        )

    # Current-year gradient line + area.
    if cur_line:
        parts.append(
            f'<path d="{cur_area}" fill="url(#linegrad)" opacity="0.22" '
            'mask="url(#areamask)" clip-path="url(#pc)"/>'
        )
        parts.append(
            f'<path d="{cur_line}" fill="none" stroke="url(#linegrad)" '
            'stroke-width="2.5" clip-path="url(#pc)"/>'
        )

    # Today marker.
    if cur_pts:
        tx, ty = cur_pts[-1]
        parts.append(
            f'<line x1="{tx:.1f}" y1="{py0}" x2="{tx:.1f}" y2="{py1}" '
            f'stroke="{MUTED}" stroke-dasharray="2 4"/>'
        )
        parts.append(
            f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="5" fill="{BG}" '
            f'stroke="{ACCENT}" stroke-width="2"/>'
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
            current_year = today.year
            activity = {
                "year": current_year,
                "today_doy": (today - date(current_year, 1, 1)).days,
                "current": weekly_series(calendar, current_year),
                "previous": weekly_series(calendar, current_year - 1),
            }

            commits_this_year = contrib["yearly"].get(current_year, {}).get("commits", 0)
            contributions_this_year = sum(
                count for day_str, count in calendar.items()
                if day_str.startswith(str(current_year))
            )
            weekly = sum(
                calendar.get((today - timedelta(days=i)).isoformat(), 0)
                for i in range(7)
            )
            days_elapsed = (today - date(current_year, 1, 1)).days + 1
            avg_per_day = contributions_this_year / days_elapsed

            grade_letter, grade_score = compute_grade({
                "commits_this_year": commits_this_year,
                "contributions_this_year": contributions_this_year,
                "prs": totals["prs"],
                "current_streak": streaks["current_length"],
                "weekly": weekly,
                "stars": profile["stars"],
                "followers": profile["followers"],
                "contributed_to": profile["contributed_to"],
            })

            data = {
                "stars": profile["stars"],
                "commits": totals["commits"],
                "prs": totals["prs"],
                "issues": totals["issues"],
                "contributed_to": profile["contributed_to"],
                "followers": profile["followers"],
                "repos": profile["repos"],
                "years": years,
                "commits_this_year": commits_this_year,
                "contributions_this_year": contributions_this_year,
                "weekly": weekly,
                "avg_per_day": avg_per_day,
                "grade_letter": grade_letter,
                "grade_score": grade_score,
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
