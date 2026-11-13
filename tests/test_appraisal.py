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


def test_multiple_narrative_fields_and_blank_primary_preserved():
    from appraisal import metadata
    data = metadata(pd.DataFrame([qrow(Remarks='', Comments='  Original\nline.  '),
                                  qrow(Remarks='First source', Comments='Second source')]))
    assert data['Remarks'].iloc[0] == '  Original\nline.  '
    assert '[Remarks]\nFirst source' in data['Remarks'].iloc[1]
    assert '[Comments]\nSecond source' in data['Remarks'].iloc[1]


def test_id_only_on_quantitative_safely_falls_back_to_unique_compound_key():
    q = qrow(**{'Assessment ID':'quant-only'})
    x = process([q], [qrow(Remarks='Source comment')])
    assert x['Comment match'].iloc[0] == 'Matched'
    assert x['Remarks'].iloc[0] == 'Source comment'


def test_resident_narratives_preserve_unmatched_unknown_and_qual_only():
    from appraisal import resident_narratives
    qual = [qrow(Remarks='Matched words'), qrow(**{'Name of Evaluator':'Other','Remarks':'Unmatched words'}),
            qrow(**{'Month of Assessment':None,'Remarks':'Undated words'}),
            qrow(**{'Resident Name':'Qual only','Remarks':'Standalone narrative'})]
    q,c = join_remarks(prepare_quantitative(pd.DataFrame([qrow()])),pd.DataFrame(qual))
    narratives = resident_narratives(q,c,'resident a','2026-01','2026-01')
    assert len(narratives) == 3
    assert set(narratives['Remarks']) == {'Matched words','Unmatched words','Undated words'}
    assert narratives['Period context'].str.contains('unknown').sum() == 1
    assert len(resident_narratives(q,c,'qual only')) == 1
    assert len(q) == 1 and q['Evaluation score'].iloc[0] == 4


def test_inline_narrative_not_duplicated_when_identical_to_qualitative():
    from appraisal import resident_narratives
    q,c = join_remarks(prepare_quantitative(pd.DataFrame([qrow(Remarks='Same text')])),pd.DataFrame([qrow(Remarks='Same text')]))
    assert len(resident_narratives(q,c,'resident a')) == 1


def test_sensitivity_exclusion_is_reversible_and_does_not_mutate():
    from appraisal import sensitivity_analysis
    q,c = synthetic_data()
    data,_ = join_remarks(prepare_quantitative(q),c)
    before = data.copy(deep=True)
    included,excluded,baseline,selected,comparison = sensitivity_analysis(data,[1])
    alpha = selected[selected['Resident Name'].eq('Resident Alpha')].iloc[0]
    assert alpha['Combined Mean (1–5)'] == 3.8
    assert len(excluded) == 1 and len(included) == 3
    assert comparison['Excluded evaluations'].sum() == 1
    pd.testing.assert_frame_equal(before,data)
    assert sensitivity_analysis(data,[])[3]['Combined Mean (1–5)'].tolist() == baseline['Combined Mean (1–5)'].tolist()


def test_sensitivity_all_excluded_preserves_residents_unranked():
    from appraisal import sensitivity_analysis
    q,c = synthetic_data()
    data,_ = join_remarks(prepare_quantitative(q),c)
    _,excluded,baseline,selected,comparison = sensitivity_analysis(data,data['Row ID'].tolist())
    assert len(selected) == len(baseline)
    assert selected['Rank'].isna().all()
    assert selected['Combined Mean (1–5)'].isna().all()
    assert selected['Total evals'].eq(0).all()
    assert comparison['Excluded evaluations'].sum() == len(data)
