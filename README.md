# SR Appraisal Dashboard

A Streamlit dashboard for reviewing Senior Resident assessment evidence during **summative departmental appraisal**. Refactored from [EPA_Dashboard](https://github.com/MucheliSS/EPA_Dashboard).

**No seniority adjustment. No sentiment scoring. No automatic bonus allocation.**

## What it shows

Two tabs keep the workflow focused: **Individual SR** and **Overall Ranking**. All qualitative comments are available within Individual SR.

- **Individual SR:** assessor profile line charts, average-domain tables with coverage counts, optional monthly trends, scores and all source narratives, including unmatched or qualitative-only records.
- **Overall ranking:** comparison bar chart plus current-period mean, median, range, ID/GM mix and assessor counts.
- **Score mapping:** choose Loose GM mapping, Tight GM mapping or ID-only; the selection applies to both tabs.
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
4. Explore the assessor profiles and optional trends. In the profile chart, use **Spotlight assessors** to show all evaluations from up to three selected assessors on the same score axis. Clear the selection to show every evaluation again. Spotlight is chart-only; the profile-month filter also affects the domain table. Neither changes narratives or rankings.
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

The sidebar score-mapping selector offers three **exploratory** options and applies consistently to **both tabs**: individual metrics, domain tables, profiles, trends and the ranking scenario. The unchanged comparison baseline uses the Loose mapping.

| Scenario | GM treatment |
|---|---|
| Loose GM mapping (default) | `(raw + 1) / 2`: 1→1, 7→4, 9→5 |
| Tight GM mapping | `(raw − 1) / 2` for raw ≥3: 3→1, 7→3, 9→4 |
| ID-only | GM records remain visible, but contribute no mapped scores |

Under the Tight mapping, raw GM values **below 3 become missing and are flagged for review**, not extrapolated below 1 or clipped. This applies independently to Overall and each domain. A withheld Overall does not enter the mean/rank denominator; domain values are not substituted for it. Source values and rows are preserved.

Changing mapping does not clear manual assessment exclusions. The ranking shows the selected mapping only, without a three-way comparison or audit columns. Individual evaluation flags remain available for reviewing source evidence. The selected mapping drives both tabs. Manual assessment exclusions apply only to the ranking sensitivity scenario; Individual SR keeps every source evaluation visible under that same mapping. The full original baseline remains available separately.

Neither numerical mapping establishes equivalent rating anchors. Tight mapping caps the highest GM value at 4, while ID can reach 5; ID-only changes the evidence mix; withholding low GM values can raise a mean. These are sensitivity checks, not validated corrections or a basis for silently discarding assessments.

## Comments and audit flags

Matching uses a unique assessment ID when available, with contextual conflict checks. Otherwise it uses resident, canonical assessor and year-month, with instrument/posting where available. **Ambiguous matches are not guessed, and joins never multiply scored rows.**

Brief or missing remarks, limited observation, partial domains and repeated evaluation keys prompt review; they never deduct points. Suspected duplicates are flagged, not automatically deleted. Automated text flags can miss context, so read the original prose.

### Narrative visibility and ranking sensitivity

The Individual SR selector includes residents found in either sheet. Its narrative section shows qualitative source rows independently of score matching, with a simple month/date and assessor heading. Source and matching details remain available in a collapsed diagnostics panel. The original month remains visible when the source omits its year; no year is inferred from another evaluation. Unconfirmed dates never enter current-period ranking. Repeated domain-score tables have been removed from narrative panels. Multiple recognised comment fields are preserved; a blank `Remarks` field no longer masks a populated `Comments` field. If no narrative text is detected, the app warns you to check the Excel headers.

Under **Overall Ranking**, select specific assessments to exclude from a temporary sensitivity scenario. The app displays excluded rows and counts, baseline versus scenario means/ranks, and an unchanged baseline table. The scenario chart, ranking and coverage tables all use the same included rows. Residents with all assessments excluded remain visible and unranked. **Restore all assessments** clears the scenario. Changing the workbook or appraisal period resets it. No source data is deleted or edited; the Individual SR tab keeps all source evaluations visible using the selected score mapping.

These controls explore sensitivity, not a validated justification for discarding unfavourable scores. Resolve appraisal decisions through the committee's documented process.

## Privacy and validation

**This app has no built-in authentication.** A private repository does not protect a deployed app. Use institution-approved hosting and access controls before uploading identifiable appraisal records.

Uploads are processed within the Streamlit session, without intentional disk storage, global data caching or external AI/NLP calls. Keep real workbooks, PDFs, comments, screenshots and exports out of Git. Review server logging, retention and backups separately.

The original Excel workbook was inspected: its qualitative sheet supplies `Month of Evaluation` without a year and uses `Type of evaluation`. These aliases are supported. Source months are displayed without guessing a year; comments remain visible independently of quantitative linkage. Rating-anchor equivalence remains unverified. Check source records and institutional appraisal rules before use.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Synthetic tests cover scoring, dates, missing data, aliases, duplicate joins, conflicts, flags, ties, Excel round-trip and Streamlit navigation. No real resident data is included.
