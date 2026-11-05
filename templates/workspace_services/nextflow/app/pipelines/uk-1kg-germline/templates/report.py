#!/usr/bin/env python3
import csv
import gzip
import html

SAMPLE = "${sample}"
REGION = "${params.region}"
VCF = "${vcf}"
COMPARISON = "${comparison}"
FLAGSTAT = "${flagstat}"
DEPTH = "${depth}"
CYP2D6 = (42126499, 42130865)  # GRCh38, Ensembl ENSG00000100197
POPS = ["GBR", "EUR", "AFR", "EAS", "SAS", "AMR"]
POP_NAMES = {
    "GBR": "British (GBR)",
    "EUR": "European",
    "AFR": "African",
    "EAS": "East Asian",
    "SAS": "South Asian",
    "AMR": "American",
}
COLOURS = {"GBR": "#0078d4", "EUR": "#8764b8", "AFR": "#038387", "EAS": "#ca5010", "SAS": "#498205", "AMR": "#986f0b"}


def esc(value):
    return html.escape(str(value))


variants = []
with gzip.open(VCF, "rt") as handle:
    for line in handle:
        if line.startswith("#"):
            continue
        chrom, pos, _id, ref, alt, qual, filt, info, fmt, sample = line.rstrip(chr(10)).split(chr(9))[:10]
        tags = dict(item.split("=", 1) if "=" in item else (item, "") for item in info.split(";"))
        fields = dict(zip(fmt.split(":"), sample.split(":")))
        afs = {}
        for pop in POPS:
            try:
                afs[pop] = float(tags.get("AF_" + pop, "nan").split(",")[0])
            except ValueError:
                afs[pop] = float("nan")
        variants.append(
            {
                "pos": int(pos),
                "ref": ref,
                "alt": alt,
                "qual": float(qual) if qual != "." else 0.0,
                "filter": filt,
                "gt": fields.get("GT", "."),
                "dp": fields.get("DP", ""),
                "type": "SNV" if len(ref) == 1 and len(alt) == 1 else "Indel",
                "af": afs,
            }
        )

passed = [v for v in variants if v["filter"] == "PASS"]
known = [v for v in passed if v["af"]["GBR"] == v["af"]["GBR"]]
cyp = [v for v in passed if CYP2D6[0] <= v["pos"] <= CYP2D6[1]]

flagstat = open(FLAGSTAT).read().splitlines()


def flag(word):
    for line in flagstat:
        if word in line:
            return int(line.split()[0]), line
    return 0, ""


total, _ = flag("in total")
mapped, mapped_line = flag(" mapped (")
duplicates, _ = flag("duplicates")
mapped_pct = mapped_line.split("(")[1].split("%")[0] + "%" if "(" in mapped_line else ""
depth = open(DEPTH).read().strip()

comparison = []
with open(COMPARISON) as handle:
    rows = [line for line in handle if not line.startswith("#")]
    comparison = list(csv.DictReader(rows, delimiter=chr(9)))

with open("cyp2d6_variants.csv", "w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["position", "ref", "alt", "type", "genotype", "depth", "qual"] + ["af_" + p.lower() for p in POPS])
    for v in cyp:
        writer.writerow(
            [v["pos"], v["ref"], v["alt"], v["type"], v["gt"], v["dp"], round(v["qual"], 1)]
            + [("" if v["af"][p] != v["af"][p] else round(v["af"][p], 4)) for p in POPS]
        )


def fmt_af(value):
    return "–" if value != value else f"{value:.3f}"


def bar_chart(rows):
    if not rows:
        return "<p>No PASS calls in CYP2D6 have 1000 Genomes allele frequencies.</p>"
    group_w, bar_w, height, pad = 110, 14, 220, 40
    width = pad + group_w * len(rows) + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height + 70}" font-family="Segoe UI, sans-serif" font-size="11">'
    ]
    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        y = height - tick * (height - 20)
        parts.append(f'<line x1="{pad}" y1="{y:.1f}" x2="{width - 10}" y2="{y:.1f}" stroke="#edebe9"/>')
        parts.append(f'<text x="{pad - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#605e5c">{tick:.2f}</text>')
    for i, v in enumerate(rows):
        x0 = pad + i * group_w + 10
        for j, pop in enumerate(POPS):
            af = v["af"][pop]
            if af != af:
                continue
            h = af * (height - 20)
            parts.append(
                f'<rect x="{x0 + j * bar_w}" y="{height - h:.1f}" width="{bar_w - 2}" height="{h:.1f}" fill="{COLOURS[pop]}"><title>{POP_NAMES[pop]}: {af:.3f}</title></rect>'
            )
        parts.append(
            f'<text x="{x0 + 3 * bar_w}" y="{height + 16}" text-anchor="middle" fill="#323130">{v["pos"]:,}</text>'
        )
        parts.append(
            f'<text x="{x0 + 3 * bar_w}" y="{height + 30}" text-anchor="middle" fill="#605e5c">{esc(v["ref"][:6])}&gt;{esc(v["alt"][:6])}</text>'
        )
    for j, pop in enumerate(POPS):
        parts.append(
            f'<rect x="{pad + j * 100}" y="{height + 44}" width="10" height="10" fill="{COLOURS[pop]}"/>'
            f'<text x="{pad + j * 100 + 14}" y="{height + 53}" fill="#323130">{POP_NAMES[pop]}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


chart_rows = sorted([v for v in cyp if v["af"]["GBR"] == v["af"]["GBR"]], key=lambda v: -v["af"]["GBR"])[:8]
others = [p for p in POPS if p not in ("GBR", "EUR")]
differences = []
for v in known:
    values = [v["af"][p] for p in others if v["af"][p] == v["af"][p]]
    if values:
        differences.append((v["af"]["GBR"] - sum(values) / len(values), v))
differences.sort(key=lambda item: -abs(item[0]))

style = """
body { font-family: 'Segoe UI', sans-serif; color: #323130; margin: 24px; max-width: 1100px; }
h1 { font-size: 22px; font-weight: 600; } h2 { font-size: 17px; font-weight: 600; margin-top: 28px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; }
.card { box-shadow: 0 1.6px 3.6px rgba(0,0,0,.13), 0 .3px .9px rgba(0,0,0,.11); padding: 12px 16px; min-width: 150px; }
.card b { display: block; font-size: 20px; font-weight: 600; } .card span { color: #605e5c; font-size: 12px; }
table { border-collapse: collapse; margin-top: 8px; font-size: 13px; }
th, td { border-bottom: 1px solid #edebe9; padding: 5px 10px; text-align: right; } th { background: #f3f2f1; }
th:first-child, td:first-child { text-align: left; }
.note { background: #fff4ce; border-left: 4px solid #d6b656; padding: 10px 14px; font-size: 13px; }
"""

cards = [
    ("Read pairs", f"{total // 2:,}"),
    ("Mapped", mapped_pct),
    ("Duplicates", f"{duplicates:,}"),
    ("Mean depth", f"{depth}x"),
    ("PASS SNVs", f"{sum(v['type'] == 'SNV' for v in passed):,}"),
    ("PASS indels", f"{sum(v['type'] == 'Indel' for v in passed):,}"),
    ("CYP2D6 calls", f"{len(cyp)}"),
]

comparison_rows = "".join(
    "<tr>"
    + "".join(
        f"<td>{esc(r[k])}</td>"
        for k in ["Type", "True positives", "False positives", "False negatives", "Precision", "Recall", "F1"]
    )
    + "</tr>"
    for r in comparison
)
cyp_rows = "".join(
    f"<tr><td>{v['pos']:,}</td><td>{esc(v['ref'])}&gt;{esc(v['alt'])}</td><td>{v['type']}</td><td>{esc(v['gt'])}</td><td>{esc(v['dp'])}</td>"
    + "".join(f"<td>{fmt_af(v['af'][p])}</td>" for p in POPS)
    + "</tr>"
    for v in cyp
)
diff_rows = "".join(
    f"<tr><td>{v['pos']:,}</td><td>{esc(v['ref'][:12])}&gt;{esc(v['alt'][:12])}</td><td>{esc(v['gt'])}</td><td>{fmt_af(v['af']['GBR'])}</td>"
    + "".join(f"<td>{fmt_af(v['af'][p])}</td>" for p in others)
    + f"<td>{d:+.3f}</td></tr>"
    for d, v in differences[:10]
)

report = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(SAMPLE)} germline report</title><style>{style}</style></head>
<body>
<h1>1000 Genomes British sample {esc(SAMPLE)}: germline variants around CYP2D6</h1>
<p>Region {esc(REGION)} on GRCh38. Reads from the 1000 Genomes high-coverage (NYGC 30x) data were aligned with BWA-MEM,
duplicates were marked with samtools, and variants were called with bcftools. Calls are annotated with allele frequencies
from the 1000 Genomes high-coverage panel for the British (GBR) population and the continental groups.</p>
<p class="note">Research demonstration only, not for clinical use. CYP2D6 has a close pseudogene (CYP2D7) and structural
variants that short-read calling cannot resolve, so these calls cannot be used to assign CYP2D6 star alleles.</p>
<div class="cards">{"".join(f'<div class="card"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v in cards)}</div>
<h2>Comparison with the 1000 Genomes calls for {esc(SAMPLE)}</h2>
<table><thead><tr><th>Type</th><th>True positives</th><th>False positives</th><th>False negatives</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>{comparison_rows}</tbody></table>
<h2>CYP2D6 allele frequencies by population</h2>
<p>The PASS calls in CYP2D6 that are most common in British people, with their frequency in each 1000 Genomes group.</p>
{bar_chart(chart_rows)}
<h2>All PASS calls in CYP2D6 (chr22:{CYP2D6[0]:,}-{CYP2D6[1]:,})</h2>
<table><thead><tr><th>Position</th><th>Change</th><th>Type</th><th>Genotype</th><th>Depth</th>{"".join(f"<th>{p}</th>" for p in POPS)}</tr></thead><tbody>{cyp_rows or '<tr><td colspan="11">No PASS calls</td></tr>'}</tbody></table>
<h2>Where British frequencies differ most from other continental groups</h2>
<p>Calls in the region with the largest difference between the GBR frequency and the mean of the AFR, EAS, SAS and AMR frequencies.</p>
<table><thead><tr><th>Position</th><th>Change</th><th>Genotype</th><th>GBR</th>{"".join(f"<th>{p}</th>" for p in others)}<th>Difference</th></tr></thead><tbody>{diff_rows}</tbody></table>
<p style="color:#605e5c;font-size:12px">Data: 1000 Genomes Project high-coverage release (NYGC, GRCh38). Reference: GRCh38 chr22.</p>
</body></html>"""
open("report.html", "w").write(report)

nl = chr(10)
summary = [
    f"# {SAMPLE} germline variants around CYP2D6",
    "",
    f"- Region: {REGION} (GRCh38)",
    f"- Mean depth: {depth}x",
    f"- PASS calls: {len(passed)}, of which {len(cyp)} are in CYP2D6",
]
for r in comparison:
    summary.append(f"- {r['Type']}: precision {r['Precision']}, recall {r['Recall']} against the 1000 Genomes calls")
summary += [
    "",
    "See `report.html` for the population frequencies and `multiqc_report.html` for QC.",
    "",
    "Research demonstration only, not for clinical use.",
]
open("README.md", "w").write(nl.join(summary) + nl)
