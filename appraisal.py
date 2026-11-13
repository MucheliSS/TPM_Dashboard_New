"""Deterministic appraisal evidence preparation. No external services or persisted data."""
from __future__ import annotations

import re
from io import BytesIO
import numpy as np
import pandas as pd
from date_helpers import (pick_feedback_month_column, pick_feedback_year_column,
                          pick_remarks_column, feedback_month_period)

DOMAINS = ['PC', 'MK', 'SBP', 'PBLI', 'Prof', 'ICS']
SCORE_COLUMNS = DOMAINS + ['Overall']
INSTRUMENTS = {'mpe': 'ID', 'id mpe': 'ID', 'nuh id mpe': 'ID', 'sgh id mpe': 'ID',
               'ttsh id mpe': 'ID', 'gm mpe': 'GM', 'ttsh gm mpe': 'GM', 'ktph gm mpe': 'GM'}
ALIASES = {'dr suma sathyanarayana rao': 'dr suma rao'}


def norm(value):
    return '' if pd.isna(value) else re.sub(r'\s+', ' ', str(value)).strip().casefold()


def find_column(frame, candidates):
    lookup = {re.sub(r'[^a-z0-9]', '', norm(c)): c for c in frame.columns}
    for c in candidates:
        if re.sub(r'[^a-z0-9]', '', norm(c)) in lookup:
            return lookup[re.sub(r'[^a-z0-9]', '', norm(c))]
    return None


def parse_period(value, year=None):
    """Never infer a year from today's date or a submission timestamp."""
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if isinstance(value, (int, float)) and 20000 <= value <= 80000:
        period = (pd.Timestamp('1899-12-30') + pd.to_timedelta(value, unit='D')).to_period('M').to_timestamp()
    elif re.fullmatch(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', s):
        dt = pd.to_datetime(s, errors='coerce', dayfirst=True)
        period = dt.to_period('M').to_timestamp() if pd.notna(dt) else pd.NaT
    else:
        if isinstance(value, str) and not re.search(r'\b(?:19|20)\d{2}\b', s):
            if not re.search(r'[A-Za-z]', s) and year is None:
                return pd.NaT
        period = feedback_month_period(value, year)
    if year is not None and pd.notna(year):
        try:
            explicit_year = int(float(year))
            if 0 <= explicit_year <= 99:
                explicit_year += 2000
            if pd.notna(period) and explicit_year != period.year:
                return pd.NaT
        except (ValueError, TypeError):
            pass
    return period


def metadata(frame):
    out = frame.copy().reset_index(drop=True)
    out.columns = [str(c).strip() for c in out.columns]
    out['Source row'] = np.arange(len(out)) + 2
    specs = {'Resident Name': ['Resident Name', 'Resident', 'Name of Resident'],
             'Assessor original': ['Name of Evaluator', 'Assessor', 'Evaluator'],
             'Assessment Type': ['Assessment Type', 'Instrument', 'Form'],
             'Assessment ID': ['Assessment ID', 'Evaluation ID', 'Response ID'],
             'Posting': ['Posting', 'Rotation', 'Attachment', 'Site']}
    for target, options in specs.items():
        col = find_column(out, options)
        out[target] = out[col].fillna('').astype(str) if col else ''
    out['Resident key'] = out['Resident Name'].map(norm)
    out['Assessor key'] = out['Assessor original'].map(norm).replace(ALIASES)
    out['Instrument key'] = out['Assessment Type'].map(norm)
    out['Posting key'] = out['Posting'].map(norm)
    out['ID key'] = out['Assessment ID'].map(norm)
    month_col = find_column(out, ['Month of Assessment', 'Assessment Month', 'Assessment Date', 'Date of Assessment', 'EPA Month', 'Rotation Month']) or pick_feedback_month_column(out)
    # Submission dates must not silently become assessment dates.
    if month_col and any(t in norm(month_col) for t in ['submission', 'submitted', 'created', 'timestamp']):
        month_col = None
    year_col = find_column(out, ['Year of Assessment', 'Assessment Year', 'EPA Year', 'Rotation Year']) or pick_feedback_year_column(out)
    out['Period'] = pd.to_datetime([parse_period(row[month_col], row[year_col] if year_col else None)
                                  if month_col else pd.NaT for _, row in out.iterrows()])
    out['Date source'] = month_col or 'Unavailable'
    # Preserve every narrative field, not only the first header (which may be blank).
    primary = pick_remarks_column(out)
    narrative_cols = [c for c in out.columns
                      if re.search(r'\b(?:remarks?|comments?|feedback)\b', norm(c))
                      and not re.search(r'\b(?:date|month|year|time|timestamp|type|score|rating)\b', norm(c))]
    if primary and primary not in narrative_cols:
        narrative_cols.insert(0, primary)
    narrative_cols = list(dict.fromkeys(narrative_cols))
    def narrative_text(row):
        pieces = [(c, str(row[c])) for c in narrative_cols if pd.notna(row[c]) and str(row[c]).strip()]
        if len(pieces) == 1:
            return pieces[0][1]
        return '\n\n'.join(f'[{c}]\n{text}' for c, text in pieces)
    out['Remarks'] = out.apply(narrative_text, axis=1) if len(out) else pd.Series(dtype=str)
    out['Remarks source'] = ', '.join(narrative_cols) if narrative_cols else 'No narrative column detected'
    return out


def prepare_quantitative(frame):
    out = metadata(frame)
    out['Inline remarks'] = out['Remarks']
    out['Instrument group'] = out['Instrument key'].map(INSTRUMENTS).fillna('Unknown')
    out['Invalid score cells'] = 0
    for col in SCORE_COLUMNS:
        source = find_column(frame, [col])
        raw = frame[source].reset_index(drop=True) if source else pd.Series(np.nan, index=out.index)
        nums = pd.to_numeric(raw, errors='coerce')
        missing = raw.map(norm).isin(['', 'n.a', 'n.a.', 'na', 'n/a', 'nan', 'none', '-', 'not applicable']) | nums.eq(0)
        maximum = out['Instrument group'].map({'ID': 5, 'GM': 9})
        invalid = ~missing & (nums.isna() | nums.lt(1) | nums.gt(maximum))
        out['Invalid score cells'] += invalid.astype(int)
        out[f'Raw {col}'] = nums.mask(missing | invalid)
        mapped = out[f'Raw {col}'].where(out['Instrument group'].ne('GM'), (out[f'Raw {col}'] + 1) / 2)
        out[col] = mapped.where(out['Instrument group'].ne('Unknown'))
    out['Rated domains'] = out[DOMAINS].notna().sum(axis=1)
    out['Domain mean'] = out[DOMAINS].mean(axis=1)
    out['Evaluation score'] = out['Overall']
    keys = ['Resident key', 'Assessor key', 'Period', 'Instrument key', 'Posting key']
    out['Duplicate evaluation key'] = out.duplicated(keys, keep=False)
    out['Row ID'] = np.arange(len(out))
    return out


def join_remarks(quant, qualitative):
    """One result per quantitative row. Never guess duplicate or missing-key matches."""
    q = quant.copy()
    qual = metadata(qualitative)
    q['Comment match'] = 'Unmatched'
    q['Qualitative row'] = pd.Series(pd.NA, index=q.index, dtype='Int64')
    qual['Match status'] = 'Unmatched'
    used = set()
    for qi, row in q.iterrows():
        if not row['Resident key']:
            q.at[qi, 'Comment match'] = 'Missing resident'
            continue
        if row['ID key'] and qual['ID key'].ne('').any():
            candidates = qual[qual['ID key'].eq(row['ID key'])]
            peers = q[q['ID key'].eq(row['ID key'])]
            # ID collision or inconsistent identity/context never authorizes a match.
            conflict = False
            for key in ['Resident key', 'Assessor key', 'Instrument key', 'Posting key', 'Period']:
                if pd.notna(row[key]) and row[key] != '':
                    present = candidates[key].notna() & candidates[key].ne('')
                    conflict |= bool((present & candidates[key].ne(row[key])).any())
            if conflict:
                q.at[qi, 'Comment match'] = 'ID identity conflict'
                continue
        else:
            if not row['Assessor key'] or pd.isna(row['Period']):
                q.at[qi, 'Comment match'] = 'Incomplete matching key'
                continue
            keys = ['Resident key', 'Assessor key', 'Period']
            candidates = qual
            peers = q
            for key in keys:
                candidates = candidates[candidates[key].eq(row[key])]
                peers = peers[peers[key].eq(row[key])]
            # A different explicit ID must never be overridden by a compound-key match.
            if row['ID key']:
                candidates = candidates[candidates['ID key'].eq('') | candidates['ID key'].eq(row['ID key'])]
            # Use instrument/posting only when both sheets provide the field for these candidates.
            for key in ['Instrument key', 'Posting key']:
                if row[key] and len(candidates) and candidates[key].ne('').all():
                    candidates = candidates[candidates[key].eq(row[key])]
                    peers = peers[peers[key].eq(row[key])]
        if len(candidates) == 1 and len(peers) == 1 and candidates.index[0] not in used:
            j = candidates.index[0]
            # Keep a quantitative-side narrative, if any, alongside the matched one.
            original = row['Remarks']
            matched = candidates.at[j, 'Remarks']
            q.at[qi, 'Remarks'] = original if original == matched else '\n\n'.join(x for x in [original, matched] if x)
            q.at[qi, 'Comment match'] = 'Matched'
            q.at[qi, 'Qualitative row'] = int(candidates.at[j, 'Source row'])
            qual.at[j, 'Match status'] = 'Matched'
            used.add(j)
        elif len(candidates):
            q.at[qi, 'Comment match'] = 'Ambiguous match'
            for j in candidates.index:
                if qual.at[j, 'Match status'] != 'Matched':
                    qual.at[j, 'Match status'] = 'Ambiguous match'
    assert len(q) == len(quant)
    return add_flags(q), qual


def add_flags(frame):
    out = frame.copy()
    flags = []
    for _, r in out.iterrows():
        f = []
        prose = r['Remarks'].strip()
        words = len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b", prose))
        if not prose:
            f.append('Missing remarks')
        elif words < 15:
            f.append('Brief remarks' + (' on ≥4.5' if r['Evaluation score'] >= 4.5 else ''))
        if re.search(r'\b(?:1|one)[\s-]*week\b|\btoo brief\b|\blimited observation\b', prose, re.I):
            f.append('Limited observation')
        if r['Rated domains'] < 4:
            f.append('Partial domains (N.A)' if r['Rated domains'] else 'No rated domains')
        if r['Duplicate evaluation key']:
            f.append('Repeated evaluation key: review duplicates')
        if r['Invalid score cells']:
            f.append('Invalid score values')
        if r['Instrument group'] == 'Unknown':
            f.append('Unknown instrument: not scored')
        if pd.isna(r['Period']):
            f.append('Assessment period missing')
        if pd.isna(r['Evaluation score']):
            f.append('Overall missing: not ranked')
        if r['Comment match'] != 'Matched':
            f.append(r['Comment match'])
        flags.append('; '.join(f))
    out['Audit flags'] = flags
    return out


def in_period(frame, start, end):
    return frame[frame['Period'].between(pd.Timestamp(start), pd.Timestamp(end))].copy()


def resident_summary(frame):
    rows = []
    for key, group in frame[frame['Resident key'].ne('')].groupby('Resident key', sort=False):
        s = group['Evaluation score']
        rows.append({'Resident key': key, 'Resident Name': group['Resident Name'].iloc[0], 'Combined Mean (1–5)': s.mean(),
                     'Median (1–5)': s.median() if s.notna().any() else np.nan, 'Minimum': s.min(), 'Maximum': s.max(),
                     'Valid scored evals': int(s.notna().sum()), 'Total evals': len(group),
                     'ID evals': int(group['Instrument group'].eq('ID').sum()),
                     'GM evals': int(group['Instrument group'].eq('GM').sum()),
                     'Unknown evals': int(group['Instrument group'].eq('Unknown').sum()),
                     'Unique assessors': group.loc[group['Assessor key'].ne(''), 'Assessor key'].nunique(),
                     'ID mean (1–5)': s[group['Instrument group'].eq('ID')].mean(),
                     'GM mean (mapped 1–5)': s[group['Instrument group'].eq('GM')].mean(),
                     'GM mean (original 1–9)': group.loc[group['Instrument group'].eq('GM'), 'Raw Overall'].mean(),
                     'Domain coverage': f"{int(group['Rated domains'].sum())}/{6 * len(group)}",
                     'Flagged evals': int(group['Audit flags'].ne('').sum()),
                     'Context / Audit Flags': '; '.join(sorted(set('; '.join(group['Audit flags']).split('; ')) - {''}))})
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows).sort_values(['Combined Mean (1–5)', 'Resident Name'], ascending=[False, True], na_position='last')
    result.insert(0, 'Rank', result['Combined Mean (1–5)'].rank(method='min', ascending=False).astype('Int64'))
    result['Evaluation range'] = result.apply(lambda r: f"{r['Minimum']:.2f}–{r['Maximum']:.2f}" if pd.notna(r['Minimum']) else 'Not scored', axis=1)
    return result.reset_index(drop=True)


def workbook_bytes(quant, qual):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        quant.to_excel(writer, sheet_name='Quantitative', index=False)
        qual.to_excel(writer, sheet_name='Qualitative', index=False)
    return buffer.getvalue()


def synthetic_data():
    q = pd.DataFrame([
        {'Resident Name': name, 'Name of Evaluator': assessor, 'Assessment Type': kind,
         'Feedback Month': month, **{d: score for d in SCORE_COLUMNS}}
        for name, assessor, kind, month, score in [
            ('Resident Alpha', 'Assessor One', 'MPE', 'Jan 2026', 3.8),
            ('Resident Alpha', 'Assessor Two', 'MPE', 'Jan 2026', 4.8),
            ('Resident Beta', 'Assessor One', 'TTSH GM MPE', 'Feb 2026', 8.0),
            ('Resident Beta', 'Assessor Three', 'MPE', 'Mar 2026', 3.5)]])
    q.loc[3, ['SBP', 'PBLI', 'ICS']] = np.nan
    qual = q[['Resident Name', 'Name of Evaluator', 'Assessment Type', 'Feedback Month']].copy()
    qual['Remarks'] = ['Organised work and clear communication. Discuss the observed assessment context with the committee before drawing conclusions.',
                       'One-week attachment. Thanks for the work.',
                       'Consistently completed tasks and explained decisions clearly. This fictional narrative is for demonstration only, not an assessment.',
                       'Some domains were not observed in this posting. Review the domain coverage alongside the available evidence.']
    return q, qual


def resident_narratives(scores, comments, resident_key, start=None, end=None):
    """Read source comments independently of score linkage; never attach by resident alone."""
    rows = []
    for _, row in comments[comments['Resident key'].eq(resident_key)].iterrows():
        rows.append({'Source': 'Qualitative', 'Source row': row['Source row'], 'Period': row['Period'],
                     'Assessor': row['Assessor original'], 'Assessment Type': row['Assessment Type'],
                     'Remarks': row['Remarks'], 'Match status': row['Match status'], 'Remarks source': row['Remarks source']})
    for _, row in scores[scores['Resident key'].eq(resident_key)].iterrows():
        inline = row['Inline remarks']
        if not inline.strip():
            continue
        # Avoid repeating identical text copied across both sheets for the matched evaluation.
        same = comments[comments['Source row'].eq(row['Qualitative row'])] if pd.notna(row['Qualitative row']) else comments.iloc[0:0]
        if len(same) == 1 and same['Remarks'].iloc[0] == inline:
            continue
        rows.append({'Source': 'Quantitative (inline)', 'Source row': row['Source row'], 'Period': row['Period'],
                     'Assessor': row['Assessor original'], 'Assessment Type': row['Assessment Type'],
                     'Remarks': inline, 'Match status': 'Inline comment', 'Remarks source': row['Remarks source']})
    result = pd.DataFrame(rows, columns=['Source','Source row','Period','Assessor','Assessment Type','Remarks','Match status','Remarks source'])
    def scope(period):
        if pd.isna(period):
            return 'Date unknown: not used in current-period ranking'
        if start is not None and end is not None and pd.Timestamp(start) <= period <= pd.Timestamp(end):
            return 'Within selected appraisal period'
        return 'Outside selected appraisal period'
    result['Period context'] = result['Period'].map(scope)
    return result.sort_values(['Period','Source','Source row'], na_position='last').reset_index(drop=True)


def sensitivity_analysis(frame, excluded_ids):
    """Recompute a clearly separate scenario; never mutate, delete or penalize source records."""
    excluded = frame[frame['Row ID'].isin(excluded_ids)].copy()
    included = frame[~frame['Row ID'].isin(excluded_ids)].copy()
    baseline = resident_summary(frame)
    selected = resident_summary(included)
    if baseline.empty:
        return included, excluded, baseline, selected, pd.DataFrame()
    if selected.empty:
        selected = baseline.iloc[0:0].copy()
    selected = selected.set_index('Resident key').reindex(baseline['Resident key']).reset_index()
    names = baseline.set_index('Resident key')['Resident Name']
    selected['Resident Name'] = selected['Resident key'].map(names)
    for c in ['Valid scored evals','Total evals','ID evals','GM evals','Unknown evals','Unique assessors','Flagged evals']:
        selected[c] = selected[c].fillna(0).astype(int)
    selected['Rank'] = selected['Rank'].astype('Int64')
    selected['Domain coverage'] = selected['Domain coverage'].fillna('0/0')
    selected['Evaluation range'] = selected['Evaluation range'].fillna('Not scored')
    selected['Context / Audit Flags'] = selected['Context / Audit Flags'].fillna('All evaluations excluded in this scenario')
    selected = selected.sort_values(['Rank','Resident Name'], na_position='last').reset_index(drop=True)
    compare = baseline[['Resident key','Resident Name','Rank','Combined Mean (1–5)','Total evals']].rename(
        columns={'Rank':'Baseline rank','Combined Mean (1–5)':'Baseline mean','Total evals':'Baseline evaluations'})
    compare = compare.merge(selected[['Resident key','Rank','Combined Mean (1–5)','Total evals']], on='Resident key', how='left').rename(
        columns={'Rank':'Scenario rank','Combined Mean (1–5)':'Scenario mean','Total evals':'Included evaluations'})
    compare['Excluded evaluations'] = compare['Baseline evaluations'] - compare['Included evaluations']
    compare['Mean change'] = compare['Scenario mean'] - compare['Baseline mean']
    return included, excluded, baseline, selected, compare.drop(columns='Resident key')
