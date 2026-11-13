# SR Appraisal Dashboard

A Streamlit dashboard for reviewing Senior Resident assessment evidence during **summative departmental appraisal**. Refactored from [EPA_Dashboard](https://github.com/MucheliSS/EPA_Dashboard).

**No seniority adjustment. No sentiment scoring. No automatic bonus allocation.**

## What it shows

- **Individual SR:** evaluation scores, deviation from the resident’s median, domain coverage and verbatim comments.
- **Narrative audit:** scores beside comments, plus unmatched or ambiguous feedback for separate review.
- **Overall ranking:** current-period mean, median, range, ID/GM mix, assessor counts and audit flags.
- **Optional prior-posting comparison:** shared residents only; never changes the current-period ranking.

## Quick start

Python 3.11 or later:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run tpm_dashboard.py
```

1. Choose **Use synthetic demonstration** to explore fictional data and download an Excel template.
2. Upload an unencrypted `.xlsx` workbook.
3. Select the intended assessment start and end months. Check the actual date range and import warnings.
4. Read the individual narratives and instrument breakdown before using the ranking in committee discussion.

PDF exports are useful for checking structure, but are **not** supported app inputs.

## Excel format

| Sheet | Columns |
|---|---|
| `Quantitative` (required) | `Resident Name`, `Month of Assessment`, `Year of Assessment`, `Assessment Type`, `Name of Evaluator`, `PC`, `MK`, `SBP`, `PBLI`, `Prof`, `ICS`, `Overall` |
| `Qualitative` (optional) | Matching resident, assessor and assessment date fields, plus `Remarks` |

Common date, assessor and comment column aliases are supported. Optional `Assessment ID` / `Evaluation ID` and `Posting` / `Rotation` improve matching. Recognised instrument names and explicit assessor aliases are listed in the app’s import panel and in `appraisal.py`.

## Scoring rules

- **Supplied `Overall` is the primary score.** The six-domain mean is shown separately, not substituted when Overall is missing.
- ID scores remain on **1–5**. GM scores map from **1–9** using **`(raw + 1) / 2`**. Original GM scores and separate ID/GM summaries remain visible.
- This aligns endpoints, **not proven rating-anchor equivalence**. Combined results are provisional evidence. The mapping raises GM values by 0.5 versus the old `/2` method; it does not correct score inflation.
- Each valid evaluation has equal weight. Repeated assessors therefore contribute repeatedly. Median and range are evaluation-level, not assessor-severity estimates.
- Zero, blank and N.A are missing. Invalid values and unknown instruments are not scored. Partial-domain forms retain any valid supplied Overall, with coverage flagged for review.
- Only the selected assessment months enter ranking. Missing dates or resident names are excluded; missing Overall remains unranked. Filenames and submission timestamps do not determine the period.
- Ranking uses unrounded means. Exact ties share competition ranks: **1, 1, 3**. Rounded differences are not evidence of meaningful performance differences.

## Comments and audit flags

Matching uses a unique assessment ID when available, with contextual conflict checks. Otherwise it uses resident, canonical assessor and year-month, with instrument/posting where available. **Ambiguous matches are not guessed, and joins never multiply scored rows.**

Brief or missing remarks, limited observation, partial domains and repeated evaluation keys prompt review; they never deduct points. Suspected duplicates are flagged, not automatically deleted. Automated text flags can miss context, so read the original prose.

## Privacy and validation

**This app has no built-in authentication.** A private repository does not protect a deployed app. Use institution-approved hosting and access controls before uploading identifiable appraisal records.

Uploads are processed within the Streamlit session, without intentional disk storage, global data caching or external AI/NLP calls. Keep real workbooks, PDFs, comments, screenshots and exports out of Git. Review server logging, retention and backups separately.

The sample PDF supported the quantitative schema, but did not validate full Excel ingestion, qualitative linkage or scale-anchor equivalence. Check those against the original institutional records before appraisal use.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Synthetic tests cover scoring, dates, missing data, aliases, duplicate joins, conflicts, flags, ties, Excel round-trip and Streamlit navigation. No real resident data is included.
