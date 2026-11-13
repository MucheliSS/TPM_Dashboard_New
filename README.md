# SR Appraisal Dashboard

A Streamlit dashboard for reviewing Senior Resident assessment evidence during **summative departmental appraisal**. Refactored from [EPA_Dashboard](https://github.com/MucheliSS/EPA_Dashboard).

**No seniority adjustment. No sentiment scoring. No automatic bonus allocation.**

## What it shows

Two tabs keep the workflow focused: **Individual SR** and **Overall Ranking**. All qualitative comments are available within Individual SR.

- **Individual SR:** assessor profile line charts, average-domain tables with coverage counts, optional monthly trends, scores and all source narratives, including unmatched or qualitative-only records.
- **Overall ranking:** comparison bar chart plus current-period mean, median, range, ID/GM mix, assessor counts and audit flags.
- **GM mapping comparison:** current mapping, proposed mapping and ID-only, with side-by-side scores, ranks and denominators.
- **Ranking sensitivity:** temporarily exclude selected assessments, compare baseline versus scenario, and restore all assessments in one click.
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
4. Explore the assessor profiles and optional trends. Profile-month filters affect only the profile chart and domain table, not narratives or rankings.
5. Read the individual narratives and instrument breakdown before using the ranking in committee discussion.

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

## GM comparison scenarios

The ranking selector offers three **exploratory** options. The unchanged baseline and Individual SR view always use the current mapping.

| Scenario | GM treatment |
|---|---|
| Current GM mapping (default) | `(raw + 1) / 2`: 1→1, 7→4, 9→5 |
| Proposed GM mapping | `(raw − 1) / 2` for raw ≥3: 3→1, 7→3, 9→4 |
| ID-only | GM records remain visible, but contribute no mapped scores |

Under the proposed mapping, raw GM values **below 3 become missing and are flagged for review**, not extrapolated below 1 or clipped. This applies independently to Overall and each domain. A withheld Overall does not enter the mean/rank denominator; domain values are not substituted for it. Source values and rows are preserved.

All three comparisons use the **same manual assessment exclusions**. Changing mapping does not clear those exclusions. The app shows each resident’s mean, rank and scored/unscored counts, plus GM values withheld by the proposed rule. The selected scenario drives its chart, ranking and coverage table; the full original baseline remains available separately.

Neither numerical mapping establishes equivalent rating anchors. Proposed mapping caps the highest GM value at 4, while ID can reach 5; ID-only changes the evidence mix; withholding low GM values can raise a mean. These are sensitivity checks, not validated corrections or a basis for silently discarding assessments.

## Comments and audit flags

Matching uses a unique assessment ID when available, with contextual conflict checks. Otherwise it uses resident, canonical assessor and year-month, with instrument/posting where available. **Ambiguous matches are not guessed, and joins never multiply scored rows.**

Brief or missing remarks, limited observation, partial domains and repeated evaluation keys prompt review; they never deduct points. Suspected duplicates are flagged, not automatically deleted. Automated text flags can miss context, so read the original prose.

### Narrative visibility and ranking sensitivity

The Individual SR selector includes residents found in either sheet. Its narrative section shows qualitative source rows independently of score matching, with assessor, date, match status and inside/outside-period context. Unknown dates remain visible but never enter ranking. Repeated domain-score tables have been removed from narrative panels. Multiple recognised comment fields are preserved; a blank `Remarks` field no longer masks a populated `Comments` field. If no narrative text is detected, the app warns you to check the Excel headers.

Under **Overall Ranking**, select specific assessments to exclude from a temporary sensitivity scenario. The app displays excluded rows and counts, baseline versus scenario means/ranks, and an unchanged baseline table. The scenario chart, ranking and coverage tables all use the same included rows. Residents with all assessments excluded remain visible and unranked. **Restore all assessments** clears the scenario. Changing the workbook or appraisal period resets it. No source data is deleted or edited; the Individual SR tab remains baseline evidence.

These controls explore sensitivity, not a validated justification for discarding unfavourable scores. Resolve appraisal decisions through the committee's documented process.

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
