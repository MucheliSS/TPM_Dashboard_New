from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'tpm_dashboard.py')


def test_empty_and_demo_navigation():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.checkbox[0].check().run()
    assert not at.exception
    assert [tab.label for tab in at.tabs] == ['📊 Individual SR', '🏆 Overall Ranking']
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


def test_restored_charts_and_individual_navigation():
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
    next(s for s in at.selectbox if s.label == 'Choose resident').set_value('resident beta').run()
    assert not at.exception
    after_rank = [d.value for d in at.dataframe if 'Rank' in d.value.columns][0]
    assert before_rank.equals(after_rank)
    assert not any(s.value == 'Filter comments' for s in at.subheader)
    assert any('Some domains were not observed' in t.value for t in at.text)


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
    assert any('no confirmed year/date' in c.value for c in at.caption)
    for e in at.expander:
        if 'Narrative Only Assessor' in e.label:
            assert not list(e.dataframe)


def test_gm_comparison_switch_keeps_exclusions_and_baseline():
    at = AppTest.from_file(APP,default_timeout=30).run()
    at.checkbox[0].check().run()
    assert not at.exception
    assert next(s for s in at.selectbox if s.label == 'Score mapping scenario').value == 'Loose GM mapping'
    next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').set_value([1]).run()
    next(s for s in at.selectbox if s.label == 'Score mapping scenario').set_value('Tight GM mapping').run()
    assert not at.exception
    assert next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').value == [1]
    table = next(d.value for d in at.dataframe if 'Baseline mean' in d.value.columns)
    beta = table[table['Resident Name'].eq('Resident Beta')].iloc[0]
    assert beta['Baseline mean'] == 4
    assert beta['Scenario mean'] == 3.5
    next(s for s in at.selectbox if s.label == 'Score mapping scenario').set_value('ID-only').run()
    assert not at.exception
    assert next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').value == [1]
    assert any('ID-only Mean (1–5)' in d.value.columns for d in at.dataframe)
    next(s for s in at.selectbox if s.label == 'Score mapping scenario').set_value('Loose GM mapping').run()
    assert not at.exception
    assert next(m for m in at.multiselect if m.label == 'Exclude assessments from the ranking scenario').value == [1]


def test_proposed_mapping_shows_low_gm_review_rows(monkeypatch):
    import appraisal
    q,c = appraisal.synthetic_data()
    q.loc[2, appraisal.SCORE_COLUMNS] = 2
    monkeypatch.setattr(appraisal,'synthetic_data',lambda:(q,c))
    at = AppTest.from_file(APP,default_timeout=30).run()
    at.checkbox[0].check().run()
    next(s for s in at.selectbox if s.label == 'Score mapping scenario').set_value('Tight GM mapping').run()
    assert not at.exception
    next(s for s in at.selectbox if s.label == 'Choose resident').set_value('resident beta').run()
    review = next(d.value for d in at.dataframe if 'Delta vs resident median' in d.value.columns)
    gm = review[review['Assessment Type'].eq('TTSH GM MPE')].iloc[0]
    assert gm['Raw Overall'] == 2
    assert gm['Evaluation score'] != gm['Evaluation score']  # NaN, not extrapolated
    assert 'raw <3 not scored' in gm['Audit flags']


def test_global_mapping_updates_individual_domains_metrics_and_table():
    at = AppTest.from_file(APP,default_timeout=30).run()
    at.checkbox[0].check().run()
    next(s for s in at.selectbox if s.label == 'Choose resident').set_value('resident beta').run()
    assert next(m.value for m in at.metric if m.label == 'Combined mean (1–5)') == '4.00'
    next(s for s in at.selectbox if s.label == 'Score mapping scenario').set_value('Tight GM mapping').run()
    assert not at.exception
    assert next(m.value for m in at.metric if m.label == 'Combined mean (1–5)') == '3.50'
    domains = next(d.value for d in at.dataframe if 'Rated evaluations' in d.value.columns)
    assert domains.loc[domains['Domain'].eq('PC'),'Mean (1–5)'].iloc[0] == 3.5
    evidence = next(d.value for d in at.dataframe if 'Delta vs resident median' in d.value.columns)
    assert evidence.loc[evidence['Assessment Type'].eq('TTSH GM MPE'),'Evaluation score'].iloc[0] == 3.5
    next(s for s in at.selectbox if s.label == 'Score mapping scenario').set_value('ID-only').run()
    assert not at.exception
    assert next(m.value for m in at.metric if m.label == 'ID-only mean (1–5)') == '3.50'
    domains = next(d.value for d in at.dataframe if 'Rated evaluations' in d.value.columns)
    assert domains.loc[domains['Domain'].eq('PC'),'Rated evaluations'].iloc[0] == 1
    assert domains.loc[domains['Domain'].eq('ICS'),'Rated evaluations'].iloc[0] == 0
    evidence = next(d.value for d in at.dataframe if 'Delta vs resident median' in d.value.columns)
    assert evidence.loc[evidence['Assessment Type'].eq('TTSH GM MPE'),'Evaluation score'].isna().all()


def test_source_month_visible_without_technical_status_on_cards(monkeypatch):
    import appraisal
    import pandas as pd
    q,c = appraisal.synthetic_data()
    c=pd.DataFrame([{'Resident Name':'Resident Alpha','Month of Evaluation':'Dec ',
                     'Assessor':'Assessor One','Type of evaluation':'MPE','Remarks':'Verbatim original prose'}])
    monkeypatch.setattr(appraisal,'synthetic_data',lambda:(q,c))
    at=AppTest.from_file(APP,default_timeout=30).run()
    at.checkbox[0].check().run()
    assert not at.exception
    assert any(e.label == 'Dec · Assessor One' for e in at.expander)
    assert any(t.value == 'Verbatim original prose' for t in at.text)
    card=next(e for e in at.expander if e.label == 'Dec · Assessor One')
    assert not list(card.caption)
    assert not list(card.dataframe)
    assert any(e.label == 'Comment details' for e in at.expander)


def test_requested_ranking_cleanup_and_labels():
    at = AppTest.from_file(APP,default_timeout=30).run()
    at.checkbox[0].check().run()
    assert not at.exception
    selector = next(s for s in at.selectbox if s.label == 'Score mapping scenario')
    assert selector.options == ['Loose GM mapping','Tight GM mapping','ID-only']
    assert selector.value == 'Loose GM mapping'
    texts = [c.value for c in at.caption] + [s.value for s in at.subheader]
    for removed in ['Current-period summative evidence • No seniority adjustment • No automatic bonus allocation',
                    'Current-period summative standing',
                    'Committee decision support, not a complete measure of merit or service contribution. Small numeric differences and sparse evidence require judgement.',
                    'Three-way comparison: same assessment selection']:
        assert removed not in texts
    for d in at.tabs[1].dataframe:
        assert not set(d.value.columns) & {'Context / Audit Flags','Audit flags','Flagged evals','Unknown evals'}
        assert 'Scenario' not in d.value.columns
    assert any('Audit flags' in d.value.columns for d in at.tabs[0].dataframe)
    assert any(m.label == 'Exclude assessments from the ranking scenario' for m in at.multiselect)
