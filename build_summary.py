"""
build_summary.py
================

Usage:
    python build_summary.py /path/to/retraction_watch.csv docs/summary.json
"""

import sys, json, math
from datetime import datetime
import pandas as pd
import numpy as np

# ---- reason category mapping (identical to the dashboard) ----
REASON_CATEGORIES = {
  "Data and Results Issues":["unreliable results","unreliable results and/or conclusions","concerns/issues about data","error in data","original data not provided","unreliable data","error in results and/or conclusions","error in analyses","error in methods","results not reproducible","concerns/issues about results","concerns/issues about results and/or conclusions","concerns/issues about article","concerns/issues about methods","error in text","error in materials (general)","error in materials","error in cell lines/tissues","contamination of cell lines/tissues","contamination of materials (general)","contamination of materials","contamination of reagents","manipulation of results","manipulation of data","unreliable image","error in image","sabotage of materials/methods"],
  "Computer-Generated Content and AI":["computer-aided content or computer-generated content"],
  "Authorship and Ethical Concerns":["concerns/issues about authorship","concerns/issues about animal welfare","concerns/issues about human subject welfare","concerns/issues about authorship/affiliation","misconduct by author","ethical violations by author","ethical violations by company/institution/third party","false/forged authorship","false/forged affiliation","conflict of interest","lack of approval from author","lack of approval from company/institution","lack of approval from third party","lack of irb/iacuc approval and/or compliance","informed/patient consent - none/withdrawn","author unresponsive","false affiliation"],
  "Plagiarism and Duplication":["duplication of image","duplication of article","duplication of data","duplication of text","plagiarism of article","euphemisms for plagiarism","plagiarism of text","plagiarism of image","plagiarism of data","euphemisms for duplication","duplication of/in article","duplication of/in image","plagiarism of/in article"],
  "Image Manipulation and Fabrication":["manipulation of images","concerns/issues about image","falsification/fabrication of image"],
  "Investigations and Findings":["investigation by journal/publisher","investigation by company/institution","investigation by third party","investigation by ori","misconduct - official investigation/finding","investigation by office of research integrity"],
  "Peer Review and Editorial Issues":["fake peer review","rogue editor","concerns/issues with peer review","taken via peer review","compromised peer review","concerns/issues about peer review"],
  "Misconduct and Fraud":["paper mill","falsification/fabrication of data","falsification/fabrication of results","misconduct by third party","misconduct by company/institution","euphemisms for misconduct","randomly generated content","ethical violations by third party","misconduct - official investigation(s) and/or finding(s)"],
  "Procedural and Legal Issues":["legal reasons/legal threats","legal reasons and/or threats","criminal proceedings","civil proceedings","nonpayment of fees/refusal to pay","publishing ban"],
  "Withdrawal and Retraction Notices":["withdrawal","retract and replace","temporary removal","date of retraction/other unknown","notice - limited or no information","notice - lack of","notice - unable to access via current resources","upgrade/update of prior notice","updated to retraction","notice - no/limited information","updated to expression of concern","upgrade/update of prior notice(s)"],
  "Complaints and Objections":["objections by third party","objections by author(s)","objections by company/institution","complaints about author","complaints about third party","complaints about company/institution"],
  "Institutional and Policy Issues":["breach of policy by author","lack of irb/iacuc approval","concerns/issues about third party involvement","concerns/issues about referencing/attributions","cites retracted work"],
  "Miscellaneous":["copyright claims","transfer of copyright and/or ownership","error by journal/publisher","error by third party","salami slicing","hoax paper","no further action","removed","updated to correction"],
}
REASON_LOOKUP = {m: cat for cat, members in REASON_CATEGORIES.items() for m in members}

SUBJECT_SCOPE = {
    "(bls) neuroscience": "Neuroscience",
    "(hsc) biostatistics/epidemiology": "Biostatistics/Epidemiology",
    "(hsc) radiology/imaging": "Radiology/Imaging",
    "(phy) nanotechnology": "Nanotechnology",
}
SUBJECT_ORDER = ["Neuroscience", "Biostatistics/Epidemiology", "Radiology/Imaging", "Nanotechnology"]


def map_reasons(raw):
    if pd.isna(raw) or not str(raw).strip():
        return ["Other / unknown"]
    cats = set()
    for tok in str(raw).split(";"):
        tok = tok.strip().lower()
        if not tok:
            continue
        cats.add(REASON_LOOKUP.get(tok, "Other / unknown"))
    return list(cats) if cats else ["Other / unknown"]


def detect_subject(subj):
    if pd.isna(subj):
        return None
    low = str(subj).lower()
    for tag, name in SUBJECT_SCOPE.items():
        if tag in low:
            return name
    return None


def median(vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return None
    return float(np.median(vals))


def prep(df):
    df = df[df["RetractionNature"].astype(str).str.strip() == "Retraction"].copy()
    pub = pd.to_datetime(df["OriginalPaperDate"], errors="coerce")
    ret = pd.to_datetime(df["RetractionDate"], errors="coerce")
    ttr = (ret - pub).dt.days / 365.25
    df["_ttr"] = [float(t) if (pd.notna(t) and 0 <= t <= 30) else None for t in ttr]
    df["_retYear"] = [int(y) if pd.notna(y) else None for y in ret.dt.year]
    df["_subject"] = df["Subject"].apply(detect_subject)
    df["_reasons"] = df["Reason"].apply(map_reasons)
    df["_countries"] = df["Country"].apply(
        lambda c: [x.strip() for x in str(c).split(";") if x.strip()] if pd.notna(c) else []
    )
    df["_authorCount"] = df["Author"].apply(
        lambda a: len([x for x in str(a).split(";") if x.strip()]) if pd.notna(a) else None
    )
    df["_journal"] = df["Journal"].fillna("").astype(str).str.strip()
    df["_publisher"] = df["Publisher"].fillna("").astype(str).str.strip()
    return df


def _valid_ttr(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def summarize(view):
    """Compute one summary block for a filtered view (list of row dicts)."""
    n = len(view)
    ttrs = [r["_ttr"] for r in view if _valid_ttr(r["_ttr"])]
    journals = {r["_journal"] for r in view if r["_journal"]}
    countries_set = {c for r in view for c in r["_countries"]}

    # annual
    annual = {}
    for r in view:
        y = r["_retYear"]
        if y is not None and 1980 <= y <= 2026:
            annual[int(y)] = annual.get(int(y), 0) + 1

    # ttr histogram (30 bins, 0..29)
    ttr_bins = [0] * 30
    for v in ttrs:
        ttr_bins[min(29, int(v))] += 1

    # reasons
    reasons = {}
    for r in view:
        for cat in r["_reasons"]:
            reasons[cat] = reasons.get(cat, 0) + 1

    # countries (count)
    ccount = {}
    for r in view:
        for c in r["_countries"]:
            ccount[c] = ccount.get(c, 0) + 1

    # publishers
    pcount = {}
    for r in view:
        p = r["_publisher"]
        if p:
            pcount[p] = pcount.get(p, 0) + 1

    # authors: counts + median ttr by group
    groups = [("1",1,1),("2",2,2),("3",3,3),("4",4,4),("5",5,5),
              ("6-7",6,7),("8-10",8,10),("11-15",11,15),("16-20",16,20)]
    author_labels, author_counts, author_meds = [], [], []
    for lab, lo, hi in groups:
        sub = [r for r in view if r["_authorCount"] is not None and lo <= r["_authorCount"] <= hi]
        author_labels.append(lab)
        author_counts.append(len(sub))
        author_meds.append(median([r["_ttr"] for r in sub]))

    # temporal lag by PRIMARY country, >=30 dated papers, fastest+slowest 15
    bycountry = {}
    for r in view:
        if not _valid_ttr(r["_ttr"]) or not r["_countries"]:
            continue
        pc = r["_countries"][0]
        bycountry.setdefault(pc, []).append(r["_ttr"])
    lag = [{"c": c, "med": median(v), "n": len(v)} for c, v in bycountry.items() if len(v) >= 30]
    lag.sort(key=lambda x: x["med"])
    if len(lag) > 30:
        lag = lag[:15] + lag[-15:]
    overall_med = median(ttrs)

    def top(d, k):
        return sorted(d.items(), key=lambda kv: -kv[1])[:k]

    return {
        "n": n,
        "medianTTR": median(ttrs),
        "ttrN": len(ttrs),
        "journals": len(journals),
        "countries": len(countries_set),
        "annual": {str(k): annual[k] for k in sorted(annual)},
        "ttrBins": ttr_bins,
        "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "topCountries": top(ccount, 15),
        "topPublishers": top(pcount, 12),
        "authorLabels": author_labels,
        "authorCounts": author_counts,
        "authorMeds": author_meds,
        "lag": lag,
        "lagOverall": overall_med,
    }


def subject_summary(df):
    """Counts + median TTR per subject (for the 'By field' chart)."""
    out = []
    for s in SUBJECT_ORDER:
        sub = df[df["_subject"] == s]
        if len(sub) == 0:
            continue
        out.append({"subject": s, "count": int(len(sub)),
                    "medianTTR": median(list(sub["_ttr"]))})
    return out


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "retraction_watch.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "summary.json"

    print(f"Reading {csv_path} ...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = prep(df)
    print(f"Retractions: {len(df):,}")

    records = df.to_dict("records")

    def has_subject(r):
        s = r["_subject"]
        return s in SUBJECT_ORDER

    biomed = [r for r in records if has_subject(r)]
    print(f"Biomedical (four fields): {len(biomed):,}")

    views = {"__biomed": biomed, "__all": records}
    present_subjects = []
    for s in SUBJECT_ORDER:
        rows = [r for r in records if r["_subject"] == s]
        if rows:
            views[s] = rows
            present_subjects.append(s)

    summary = {
        "generated": datetime.utcnow().strftime("%Y-%m-%d"),
        "subjectsPresent": present_subjects,
        "subjectField": subject_summary(df),   # same regardless of view
        "views": {k: summarize(v) for k, v in views.items()},
    }

    with open(out_path, "w") as f:
        json.dump(summary, f, separators=(",", ":"))
    size = len(json.dumps(summary))
    print(f"Wrote {out_path}  ({size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
