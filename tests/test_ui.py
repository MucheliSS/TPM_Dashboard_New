from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'tpm_dashboard.py')


def test_empty_and_demo_navigation():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.checkbox[0].check().run()
    assert not at.exception
    assert len(at.tabs) == 3
    assert len(at.dataframe) > 3
    # Repeated resident selections and changing the period must rerender safely.
    resident = next(s for s in at.selectbox if s.label == 'Choose resident')
    resident.set_value('resident beta').run()
    assert not at.exception
    end = next(s for s in at.selectbox if s.label.startswith('End month'))
    end.select_index(0).run()
    assert not at.exception
    at.checkbox[0].uncheck().run()
    assert not at.exception
    at.checkbox[0].check().run()
    assert not at.exception


def test_restored_charts_filters_and_reset():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.checkbox[0].check().run()
    assert not at.exception
    assert len(at.get('plotly_chart')) == 3
    assert any(s.value == 'Average domain scores' for s in at.subheader)
    # A profile-month selection does not change the appraisal-period ranking.
    profile = next(s for s in at.selectbox if s.label == 'Profile month')
    profile.select_index(1).run()
    assert not at.exception
    before_rank = [d.value for d in at.dataframe if 'Rank' in d.value.columns][0]
    # Literal search with no match, then reset.
    next(t for t in at.text_input if t.label == 'Search remarks').set_value('no matching prose xyz').run()
    assert not at.exception
    assert any('No evaluation comments match' in i.value for i in at.info)
    after_rank = [d.value for d in at.dataframe if 'Rank' in d.value.columns][0]
    assert before_rank.equals(after_rank)
    next(t for t in at.text_input if t.label == 'Search remarks').set_value('').run()
    next(m for m in at.multiselect if m.label == 'Residents').set_value(['resident beta']).run()
    assert not at.exception
    evidence = [d.value for d in at.dataframe if 'Evaluation score' in d.value.columns and 'Delta vs resident median' not in d.value.columns][0]
    assert evidence['Resident Name'].eq('Resident Beta').all()
    next(m for m in at.multiselect if m.label == 'Residents').set_value([]).run()
    assert not at.exception


def test_sensitivity_controls_exclude_restore_and_period_reset():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.checkbox[0].check().run()
    assert not at.exception
    next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').set_value([1]).run()
    assert not at.exception
    assert any('Sensitivity scenario active' in w.value for w in at.warning)
    comparison = next(d.value for d in at.dataframe if 'Baseline mean' in d.value.columns)
    alpha = comparison[comparison['Resident Name'].eq('Resident Alpha')].iloc[0]
    assert round(alpha['Baseline mean'],2) == 4.3
    assert alpha['Scenario mean'] == 3.8
    # Individual summary stays baseline; only ranking tab uses the scenario.
    assert next(m.value for m in at.metric if m.label == 'Combined mean (1–5)') == '4.30'
    next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').set_value([0,1,2,3]).run()
    assert not at.exception
    next(b for b in at.button if b.label == 'Restore all assessments').click().run()
    assert not at.exception
    assert next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').value == []
    next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').set_value([1]).run()
    next(s for s in at.selectbox if s.label.startswith('End month')).select_index(0).run()
    assert not at.exception
    assert next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').value == []


def test_individual_shows_qualitative_only_and_unmatched_comments(monkeypatch):
    import appraisal
    import pandas as pd
    q,c = appraisal.synthetic_data()
    extra = c.iloc[[0]].copy()
    extra['Resident Name'] = 'Resident Gamma'
    extra['Name of Evaluator'] = 'Narrative Only Assessor'
    extra['Feedback Month'] = None
    extra['Remarks'] = 'Qualitative-only original\ncomment with retained formatting.'
    unmatched = c.iloc[[0]].copy()
    unmatched['Name of Evaluator'] = 'Another Assessor'
    unmatched['Remarks'] = 'Unmatched Alpha narrative.'
    c = pd.concat([c,extra,unmatched], ignore_index=True)
    monkeypatch.setattr(appraisal,'synthetic_data',lambda:(q,c))
    at = AppTest.from_file(APP,default_timeout=30).run()
    at.checkbox[0].check().run()
    assert not at.exception
    assert any(t.value == 'Unmatched Alpha narrative.' for t in at.text)
    next(s for s in at.selectbox if s.label == 'Choose resident').set_value('resident gamma').run()
    assert not at.exception
    assert any(t.value == 'Qualitative-only original\ncomment with retained formatting.' for t in at.text)
    assert any('Date unknown: not used' in c.value for c in at.caption)
    for e in at.expander:
        if 'Narrative Only Assessor' in e.label:
            assert not list(e.dataframe)
