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
