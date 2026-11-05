"""Builds an HTML report comparing a sample's variants with British and global allele frequencies."""

import argparse
import csv
import html

GROUPS = ["GBR", "EUR", "AFR", "EAS", "SAS", "AMR"]
OTHERS = ["AFR", "EAS", "SAS", "AMR"]
BINS = [
    ("Not in 1000 Genomes", None, None),
    ("< 1%", 0, 0.01),
    ("1–5%", 0.01, 0.05),
    ("5–20%", 0.05, 0.2),
    ("20–50%", 0.2, 0.5),
    ("≥ 50%", 0.5, 1.01),
]


def number(value):
    try:
        return float(value.split(",")[0])
    except ValueError:
        return None


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            chrom, pos, ref, alt, qual, gt, *afs = line.rstrip("\n").split("\t")
            if gt.replace("|", "/") in ("0/0", "./.", "."):
                continue
            af = dict(zip(GROUPS, (number(a) for a in afs), strict=True))
            rows.append(
                {
                    "id": f"{chrom}:{pos} {ref}>{alt}",
                    "type": "SNV" if len(ref) == len(alt) == 1 else "Indel",
                    "gt": gt,
                    "qual": qual,
                    **af,
                }
            )
    return rows


def pct(v):
    return "–" if v is None else f"{v * 100:.1f}%"


def table(rows, columns):
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in columns) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def chart(counts):
    width, bar_h, gap = 520, 22, 8
    top = max(counts.values()) or 1
    parts = []
    for i, (label, n) in enumerate(counts.items()):
        y = i * (bar_h + gap)
        w = int((width - 200) * n / top)
        parts.append(
            f'<text x="0" y="{y + 16}" font-size="13">{html.escape(label)}</text>'
            f'<rect x="160" y="{y}" width="{w}" height="{bar_h}" fill="#0078d4"/>'
            f'<text x="{165 + w}" y="{y + 16}" font-size="13">{n}</text>'
        )
    return f'<svg width="{width}" height="{len(counts) * (bar_h + gap)}">{"".join(parts)}</svg>'


def write_csv(path, rows, columns):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--max-af", type=float, default=0.01)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    rows = load(args.table)
    counts = {label: 0 for label, _, _ in BINS}
    for r in rows:
        for label, low, high in BINS:
            if (low is None and r["GBR"] is None) or (
                low is not None and r["GBR"] is not None and low <= r["GBR"] < high
            ):
                counts[label] += 1
                break

    rare = [r for r in rows if r["GBR"] is None or r["GBR"] < args.max_af]
    for r in rows:
        diffs = [(abs(r["GBR"] - r[g]), g) for g in OTHERS if r["GBR"] is not None and r[g] is not None]
        r["diff"], r["most_different_from"] = max(diffs) if diffs else (0.0, "")
    differentiated = sorted((r for r in rows if r["diff"] > 0), key=lambda r: r["diff"], reverse=True)[: args.top]

    columns = ["id", "type", "gt", "qual", *GROUPS]
    shown = lambda rs: [{**r, **{g: pct(r[g]) for g in GROUPS}} for r in rs]  # noqa: E731
    write_csv("rare_in_gbr.csv", rare, columns)
    write_csv("differentiated.csv", differentiated, [*columns, "diff", "most_different_from"])

    snvs = sum(r["type"] == "SNV" for r in rows)
    hom = sum(r["gt"].replace("|", "/") == "1/1" for r in rows)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>British population comparison</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#323130}}h1{{font-weight:600}}
table{{border-collapse:collapse;margin:8px 0 24px}}td,th{{border:1px solid #edebe9;padding:4px 8px;font-size:13px;text-align:left}}
th{{background:#f3f2f1}}.cards{{display:flex;gap:16px}}.card{{border:1px solid #edebe9;padding:12px 16px;border-radius:4px}}
.card b{{display:block;font-size:24px}}.note{{color:#605e5c;font-size:13px}}</style></head><body>
<h1>British population comparison</h1>
<p class="note">{html.escape(args.title)}. Allele frequencies are from 1000 Genomes: GBR (British in England and Scotland) and the
EUR, AFR, EAS, SAS and AMR continental groups. Research demonstration only.</p>
<div class="cards">
<div class="card"><b>{len(rows)}</b>variants called</div>
<div class="card"><b>{snvs}</b>SNVs</div>
<div class="card"><b>{len(rows) - snvs}</b>indels</div>
<div class="card"><b>{hom}</b>homozygous</div>
<div class="card"><b>{len(rare)}</b>rare in GBR (&lt; {args.max_af * 100:g}%) or absent</div>
</div>
<h2>British allele frequency of the sample's variants</h2>
{chart(counts)}
<h2>Rare in British people</h2>
<p class="note">Variants with a GBR frequency below {args.max_af * 100:g}%, or not seen in 1000 Genomes. Also in rare_in_gbr.csv.</p>
{table(shown(rare[:50]), columns)}
<h2>Most different from other populations</h2>
<p class="note">The largest absolute differences between GBR and the AFR, EAS, SAS or AMR frequency. Also in differentiated.csv.</p>
{table([{**r, "diff": pct(r["diff"])} for r in shown(differentiated)], [*columns, "diff", "most_different_from"])}
</body></html>"""
    with open("report.html", "w") as f:
        f.write(page)


if __name__ == "__main__":
    main()
