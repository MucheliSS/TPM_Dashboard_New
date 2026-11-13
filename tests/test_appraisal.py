import io
import numpy as np
import pandas as pd
import pytest
from appraisal import *


def qrow(**changes):
    r = {'Resident Name': 'Resident A', 'Name of Evaluator': 'Assessor One',
         'Month of Assessment': ' Jan ', 'Year of Assessment': 2026.00,
         'Assessment Type': 'MPE', **{d: 4 for d in SCORE_COLUMNS}}
    r.update(changes)
    return r


def process(rows, remarks=None):
    return join_remarks(prepare_quantitative(pd.DataFrame(rows)), pd.DataFrame(remarks or []))[0]


@pytest.mark.parametrize('raw,expected', [(1,1),(5,3),(7,4),(8,4.5),(9,5)])
def test_gm_endpoints(raw, expected):
    x = process([qrow(**{'Assessment Type':'GM MPE', 'Overall':raw})])
    assert x['Evaluation score'].iloc[0] == expected
    assert x['Raw Overall'].iloc[0] == raw


def test_supplied_overall_primary():
    x = process([qrow(Overall=3)])
    assert x['Evaluation score'].iloc[0] == 3
    assert x['Domain mean'].iloc[0] == 4
    x = process([qrow(Overall=None)])
    assert pd.isna(resident_summary(x)['Rank'].iloc[0])


def test_zero_na_partial_invalid_unknown():
    x = process([qrow(PC=0, MK='N.A', SBP='', PBLI=None), qrow(PC=6, Overall='bad'), qrow(**{'Assessment Type':'unrecognised'})])
    assert x['Rated domains'].tolist() == [2,5,0]
    assert x['Invalid score cells'].tolist() == [0,2,0]
    assert pd.isna(x['Evaluation score'].iloc[2])
    assert 'Partial domains' in x['Audit flags'].iloc[0]


def test_all_missing():
    x = process([qrow(**{d:'N.A' for d in SCORE_COLUMNS})])
    assert x['Rated domains'].iloc[0] == 0
    assert pd.isna(x['Domain mean'].iloc[0])
    assert pd.isna(x['Evaluation score'].iloc[0])


def test_alias_verbatim_and_year_join():
    q = [qrow(**{'Name of Evaluator':' Dr Suma Sathyanarayana Rao '}), qrow(**{'Year of Assessment':2025})]
    prose = 'First line.\n Second line.  Spacing retained.'
    qual = [qrow(**{'Name of Evaluator':'Dr Suma Rao','Remarks':prose})]
    x = process(q, qual)
    assert x['Remarks'].tolist() == [prose,'']
    assert x['Comment match'].tolist() == ['Matched','Unmatched']


def test_duplicate_quant_never_multiplies():
    x = process([qrow(),qrow()], [qrow(Remarks='hello')])
    assert len(x) == 2
    assert x['Comment match'].eq('Ambiguous match').all()


def test_duplicate_qual_never_multiplies():
    x = process([qrow()], [qrow(Remarks='one'),qrow(Remarks='two')])
    assert len(x) == 1
    assert x['Comment match'].iloc[0] == 'Ambiguous match'


def test_missing_keys_never_join():
    q = qrow(**{'Name of Evaluator':''})
    assert process([q], [dict(q, Remarks='unsafe')])['Remarks'].iloc[0] == ''


def test_id_conflict():
    q = qrow(**{'Assessment ID':'123'})
    r = dict(q, **{'Name of Evaluator':'Another Assessor','Remarks':'do not attach'})
    x = process([q],[r])
    assert x['Remarks'].iloc[0] == ''
    assert 'conflict' in x['Comment match'].iloc[0]


def test_id_uniquely_links():
    q = qrow(**{'Assessment ID':'123'})
    assert process([q],[dict(q,Remarks='hello')])['Remarks'].iloc[0] == 'hello'


def test_flags_not_score_penalties():
    x = process([qrow(Overall=5)], [qrow(Remarks='One-week observation only.')])
    assert x['Evaluation score'].iloc[0] == 5
    assert 'Limited observation' in x['Audit flags'].iloc[0]
    assert 'Brief remarks on ≥4.5' in x['Audit flags'].iloc[0]


def test_assessment_date_priority_and_missing_year():
    x = process([qrow(**{'Feedback Month':'Jun 2026'})])
    assert x['Period'].iloc[0] == pd.Timestamp('2026-01-01')
    x = process([qrow(**{'Year of Assessment':None})])
    assert pd.isna(x['Period'].iloc[0])


@pytest.mark.parametrize('v,y,expected', [('Jan 2026',None,'2026-01-01'),('2026-02',None,'2026-02-01'),
                                         ('Jan',2025.00,'2025-01-01'),(3,2026,'2026-03-01'),
                                         ('31/03/2026',None,'2026-03-01')])
def test_date_formats(v,y,expected):
    assert parse_period(v,y) == pd.Timestamp(expected)


def test_period_filter():
    x = process([qrow(), qrow(**{'Year of Assessment':2025}),qrow(**{'Month of Assessment':'Feb'})])
    assert len(in_period(x,'2026-01-01','2026-01-01')) == 1


def test_rank_full_precision_and_exact_ties():
    x = process([qrow(Overall=3.501),qrow(**{'Resident Name':'B','Overall':3.504}),
                 qrow(**{'Resident Name':'C','Overall':3.504}),qrow(**{'Resident Name':'D','Overall':None})])
    r = resident_summary(x)
    assert r['Resident Name'].tolist() == ['B','C','Resident A','D']
    assert r['Rank'].iloc[:3].tolist() == [1,1,3]
    assert pd.isna(r['Rank'].iloc[-1])


def test_repeated_assessors_evaluation_weight():
    x = process([qrow(Overall=3),qrow(Overall=3),qrow(**{'Name of Evaluator':'Other','Overall':5})])
    r = resident_summary(x).iloc[0]
    assert r['Combined Mean (1–5)'] == pytest.approx(11/3)
    assert r['Median (1–5)'] == 3
    assert r['Unique assessors'] == 2


def test_synthetic_excel_roundtrip():
    q, qual = synthetic_data()
    blob = workbook_bytes(q,qual)
    book = pd.ExcelFile(io.BytesIO(blob))
    assert book.sheet_names == ['Quantitative','Qualitative']
    a,b = join_remarks(prepare_quantitative(pd.read_excel(book,'Quantitative')), pd.read_excel(book,'Qualitative'))
    assert len(a) == 4
    assert a['Comment match'].eq('Matched').all()


def test_empty_workbook_rows_safe():
    a,b = join_remarks(prepare_quantitative(pd.DataFrame()), pd.DataFrame())
    assert a.empty and b.empty
    assert resident_summary(a).empty

@pytest.mark.parametrize('value', ['Jan 15', '31/03/2025', 45747])
def test_conflicting_year_is_not_silently_overwritten(value):
    assert pd.isna(parse_period(value, 2026))


def test_duplicate_key_visible_without_qualitative():
    x = process([qrow(), qrow()])
    assert x['Audit flags'].str.contains('Repeated evaluation key').all()
