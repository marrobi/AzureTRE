#!/usr/bin/env python3
import csv
import glob
import html
import json
import os
import shutil
import statistics

title = json.loads("""${title_json}""")
palette = ["#0078d4", "#8764b8", "#038387", "#ca5010", "#498205", "#c239b3", "#986f0b", "#004e8c"]

series = {}
for path in sorted(glob.glob("*.csv")):
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            series.setdefault(row["sample"], []).append(float(row["value"]))

rows = []
for sample, values in series.items():
    rows.append(
        {
            "sample": sample,
            "steps": len(values),
            "mean": round(statistics.fmean(values), 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "final": round(values[-1], 3),
        }
    )

with open("summary.csv", "w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["sample", "steps", "mean", "min", "max", "final"])
    writer.writeheader()
    writer.writerows(rows)

os.makedirs("samples", exist_ok=True)
for path in glob.glob("*.csv"):
    if path != "summary.csv":
        shutil.copy(path, os.path.join("samples", path))

width, height, pad = 720, 360, 40
all_values = [v for values in series.values() for v in values] or [0.0]
low, high = min(all_values), max(all_values)
span = (high - low) or 1.0
longest = max((len(v) for v in series.values()), default=1)


def point(i, v):
    x = pad + (width - 2 * pad) * i / max(longest - 1, 1)
    y = height - pad - (height - 2 * pad) * (v - low) / span
    return f"{x:.1f},{y:.1f}"


lines = []
for n, (sample, values) in enumerate(series.items()):
    colour = palette[n % len(palette)]
    pts = " ".join(point(i, v) for i, v in enumerate(values))
    lines.append(
        f'<polyline fill="none" stroke="{colour}" stroke-width="2" points="{pts}"><title>{html.escape(sample)}</title></polyline>'
    )
    lines.append(
        f'<text x="{width - pad + 4}" y="{pad + 16 * n}" font-size="12" fill="{colour}">{html.escape(sample)}</text>'
    )

zero = height - pad - (height - 2 * pad) * (0 - low) / span
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width + 120} {height}" font-family="Segoe UI, sans-serif">'
    f'<rect width="100%" height="100%" fill="#ffffff"/>'
    f'<text x="{pad}" y="24" font-size="16" fill="#323130">{html.escape(title)}: simulated trajectories</text>'
    f'<line x1="{pad}" y1="{zero:.1f}" x2="{width - pad}" y2="{zero:.1f}" stroke="#c8c6c4" stroke-dasharray="4 4"/>'
    f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="#8a8886"/>'
    f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#8a8886"/>'
    + "".join(lines)
    + "</svg>"
)
with open("trajectories.svg", "w") as handle:
    handle.write(svg)

table = "".join(
    "<tr>"
    + "".join(f"<td>{html.escape(str(r[k]))}</td>" for k in ("sample", "steps", "mean", "min", "max", "final"))
    + "</tr>"
    for r in rows
)
report = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; color: #323130; margin: 24px; }}
h1 {{ font-weight: 600; font-size: 22px; }}
table {{ border-collapse: collapse; margin-top: 16px; }}
th, td {{ border-bottom: 1px solid #edebe9; padding: 6px 12px; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ background: #f3f2f1; }}
</style></head>
<body>
<h1>{html.escape(title)}</h1>
<p>{len(rows)} samples simulated with {longest} steps each.</p>
{svg}
<table><thead><tr><th>Sample</th><th>Steps</th><th>Mean</th><th>Min</th><th>Max</th><th>Final</th></tr></thead>
<tbody>{table}</tbody></table>
</body></html>
"""
with open("report.html", "w") as handle:
    handle.write(report)

best = max(rows, key=lambda r: r["final"]) if rows else None
with open("README.md", "w") as handle:
    handle.write(f"# {title}" + chr(10) + chr(10))
    handle.write(f"- Samples: {len(rows)}" + chr(10))
    handle.write(f"- Steps per sample: {longest}" + chr(10))
    if best:
        handle.write(f"- Highest final value: **{best['sample']}** ({best['final']})" + chr(10))
    handle.write(chr(10) + "See `report.html` for the chart and summary table." + chr(10))
