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
