import numpy as np
import pandas as pd
from appraisal import synthetic_data, prepare_quantitative, join_remarks, resident_summary
from visualizations import profile_figure, domain_summary, temporal_figure, comparison_figure, filter_comments


def records():
    q,c = synthetic_data()
    return join_remarks(prepare_quantitative(q),c)[0]


def test_profile_keeps_one_trace_per_evaluation_and_gaps():
    data = records()
    data.loc[1,'Assessor original'] = data.loc[0,'Assessor original']
    data.loc[0,'MK'] = np.nan
    fig = profile_figure(data)
    assert len(fig.data) == len(data)
    assert len({trace.name for trace in fig.data}) == len(data)
    assert all(trace.connectgaps is False for trace in fig.data)
    assert len(fig.data[0].y) == 6
    assert pd.isna(fig.data[0].y[1])


def test_domain_summary_counts_only_rated_cells():
    data = records()
    table = domain_summary(data).set_index('Domain')
    assert table.at['ICS','Rated evaluations'] == 3
    assert table.at['ICS','Total evaluations'] == 4
    assert table.at['PC','Rated evaluations'] == 4


def test_temporal_gaps_and_excludes_missing_dates():
    data = records()
    data = data[data['Period'].ne(pd.Timestamp('2026-02-01'))].copy()
    data.loc[data.index[0],'Period'] = pd.NaT
    fig = temporal_figure(data)
    assert len(fig.data) == 6
    assert all(t.connectgaps is False for t in fig.data)
    assert all(pd.Timestamp('2026-02-01') in pd.to_datetime(t.x) for t in fig.data)
    for trace in fig.data:
        assert pd.isna(trace.y[1])


def test_bar_excludes_unranked_and_uses_zero_baseline():
    data = records()
    data.loc[data['Resident key'].eq('resident beta'),'Evaluation score'] = np.nan
    fig = comparison_figure(resident_summary(data))
    assert list(fig.data[0].x) == ['Resident Alpha']
    assert fig.layout.yaxis.range[0] == 0


def test_literal_comment_filters_do_not_mutate_input():
    data = records()
    before = data.copy(deep=True)
    assert len(filter_comments(data, residents=['resident alpha'])) == 2
    assert len(filter_comments(data, assessors=['assessor one'], months=['2026-02'])) == 1
    assert filter_comments(data, query='.*').empty
    assert len(filter_comments(data, query='ONE-WEEK')) == 1
    data.loc[0,'Period'] = pd.NaT
    assert len(filter_comments(data, months=['Unknown month'])) == 1
    pd.testing.assert_frame_equal(before.iloc[1:],data.iloc[1:])


def test_profile_spotlight_keeps_all_selected_evaluations_and_stable_styles():
    from visualizations import assessor_chart_styles, assessment_chart_dashes, profile_chart_options

    data = records()
    repeated = data.iloc[[0]].copy()
    repeated['Source row'] = 100
    repeated['Assessor original'] = 'Assessor One (alias)'
    data = pd.concat([data, repeated], ignore_index=True)
    styles = assessor_chart_styles(data)
    dashes = assessment_chart_dashes(data)
    resident = data[data['Resident key'].eq('resident alpha')]
    full = profile_figure(resident, styles=styles, evaluation_dashes=dashes)
    filtered = profile_figure(resident, styles=styles, spotlight=('assessor one',),
                              evaluation_dashes=dashes)
    original = {trace.name: trace for trace in full.data}
    assert len(filtered.data) == resident['Assessor key'].eq('assessor one').sum() == 2
    assert len({trace.line.dash for trace in filtered.data}) == 2
    assert len({(trace.line.color, trace.marker.symbol) for trace in filtered.data}) == 1
    for trace in filtered.data:
        assert trace.line == original[trace.name].line
        assert trace.marker == original[trace.name].marker
    assert full.layout.yaxis.range == filtered.layout.yaxis.range
    assert full.layout.yaxis.fixedrange and filtered.layout.yaxis.fixedrange
    assert profile_chart_options(data)['assessor one'] == 'Assessor One'
    assert len(set(styles.values())) == len(styles)


def test_profile_labels_skip_tied_endpoints_and_keep_readable_ticks():
    from appraisal import DOMAINS

    data = records().iloc[:3].copy()
    data[DOMAINS[-1]] = [2, 2, 4]
    fig = profile_figure(data)
    assert [label.y for label in fig.layout.annotations] == [4]
    assert fig.layout.xaxis.tickfont.size == 16
    assert fig.layout.yaxis.title.font.size == 18
    assert all(trace.line.width == 3 for trace in fig.data)
