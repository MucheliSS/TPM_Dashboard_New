"""Summative appraisal evidence dashboard. Run: streamlit run tpm_dashboard.py."""
from io import BytesIO
from hashlib import sha256
import pandas as pd
import streamlit as st
from appraisal import (DOMAINS, INSTRUMENTS, ALIASES, prepare_quantitative, join_remarks,
                       in_period, resident_summary, synthetic_data, workbook_bytes, resident_narratives, sensitivity_analysis, GM_SCENARIOS, apply_gm_scenario, narrative_date_label)

from visualizations import (assessment_chart_dashes, assessor_chart_styles, profile_chart_options,
                            profile_figure, domain_summary, temporal_figure, comparison_figure)

st.set_page_config(page_title='SR appraisal evidence', page_icon='📊', layout='wide')
st.title('Senior Resident appraisal evidence')
st.info('GM score scenarios are exploratory, not proof that rating anchors are equivalent. Read the ID/GM breakdown and narratives before making appraisal judgements.')


def load_workbook(blob):
    book = pd.ExcelFile(BytesIO(blob), engine='openpyxl')
    names = {s.strip().casefold(): s for s in book.sheet_names}
    if 'quantitative' not in names:
        raise ValueError('A Quantitative sheet is required.')
    q = pd.read_excel(book, sheet_name=names['quantitative'])
    qualitative = pd.read_excel(book, sheet_name=names['qualitative']) if 'qualitative' in names else pd.DataFrame()
    return join_remarks(prepare_quantitative(q), qualitative)


with st.sidebar:
    st.header('Appraisal period')
    upload = st.file_uploader('Current-period workbook', type=['xlsx'])
    demo = st.checkbox('Use synthetic demonstration', value=False)
    st.caption('Excel only. PDF exports are useful for schema review, but cannot be uploaded here. Files are processed in this session; do not deploy without access controls.')

if demo:
    dataset_key = 'synthetic-v1'
    q, comments = synthetic_data()
    scores, comments = join_remarks(prepare_quantitative(q), comments)
    st.warning('Demonstration: all names, scores and comments below are fictional.')
    st.download_button('Download synthetic Excel template', workbook_bytes(q, synthetic_data()[1]), 'synthetic_appraisal_template.xlsx')
elif upload:
    try:
        dataset_key = sha256(upload.getvalue()).hexdigest()[:16]
        scores, comments = load_workbook(upload.getvalue())
    except Exception as exc:
        st.error(f'Cannot read workbook: {type(exc).__name__}. Check that it is an unencrypted .xlsx with a Quantitative sheet and valid headers.')
        st.stop()
else:
    st.write('Upload your Excel workbook, or choose the synthetic demonstration in the sidebar.')
    st.stop()

periods = sorted(scores['Period'].dropna().unique())
with st.sidebar:
    if periods:
        labels = [pd.Timestamp(p).strftime('%Y-%m') for p in periods]
        start = st.selectbox('Start month (inclusive)', labels, index=0)
        end = st.selectbox('End month (inclusive)', labels, index=len(labels)-1)
        if start > end:
            st.error('End month must not precede start month.')
            st.stop()
        current = in_period(scores, start, end)
        st.caption('Choose the intended period explicitly. Workbook filenames are not used to infer assessment dates.')
    else:
        st.error('No assessment year-month could be parsed. Rankings are unavailable until dates are corrected.')
        current = scores.iloc[0:0].copy()
    previous = st.file_uploader('Optional prior-posting workbook', type=['xlsx'])
    st.subheader('Score mapping')
    gm_scenario = st.selectbox('Score mapping scenario', list(GM_SCENARIOS), key=f'gm_{dataset_key}')
    st.caption(GM_SCENARIOS[gm_scenario])
    if gm_scenario == 'Tight GM mapping':
        st.warning('The Tight mapping caps GM at 4 while ID can reach 5. Withholding GM values below 3 can raise a mean by changing its denominator. This is a sensitivity check, not a validated fairness correction.')
    elif gm_scenario == 'ID-only':
        st.info('ID-only changes the evidence mix. GM-only residents remain visible but unranked in this scenario.')
    st.caption('Exploratory comparisons, not validated scale equivalence. The selected mapping applies to both tabs. The Loose mapping remains the unchanged comparison baseline. Changing this selector does not clear manual exclusions.')

scenario_current = apply_gm_scenario(current, gm_scenario)
st.caption(f'Active score mapping: {gm_scenario}. Applies to Individual SR and Overall Ranking.')


with st.expander('Import validation and scoring rules', expanded=False):
    a, b, c, d = st.columns(4)
    a.metric('Quantitative rows', len(scores))
    b.metric('In selected period', len(current))
    c.metric('Missing assessment period', int(scores['Period'].isna().sum()))
    d.metric('Unmatched / ambiguous comments', int(comments['Match status'].ne('Matched').sum()))
    st.write(f"Detected assessment date source: {', '.join(scores['Date source'].unique()) or 'None'}")
    if periods:
        st.write(f"Actual assessment range: {pd.Timestamp(periods[0]):%b %Y} to {pd.Timestamp(periods[-1]):%b %Y}")
    st.write('Primary score: supplied Overall. Domain mean is shown separately and is not substituted when Overall is missing. Each valid evaluation receives equal weight; repeated assessors therefore contribute repeatedly. Median and range are evaluation-level, not rater-severity estimates.')
    st.write('Baseline GM mapping: (raw + 1) ÷ 2. The active scenario is selected in the sidebar. Zero and N.A are unrated. Invalid scores and unknown instruments are not scored. Current-period ranking excludes missing dates and missing resident names. Flags prompt review and never deduct points.')
    st.write('Ranks use full-precision means and exact ties share the minimum rank (1, 1, 3). Display rounding is not a test of meaningful difference.')
    st.json({'Recognised instruments': INSTRUMENTS, 'Explicit assessor aliases': ALIASES}, expanded=False)
    st.dataframe(scores[['Instrument group', 'Comment match']].value_counts().rename('Rows').reset_index(), hide_index=True)
    invalid = scores[scores['Invalid score cells'].gt(0) | scores['Instrument group'].eq('Unknown') | scores['Period'].isna() | scores['Resident key'].eq('')]
    if len(invalid):
        st.warning(f'{len(invalid)} rows need import review. Unknown dates cannot enter the current-period ranking.')
        st.dataframe(invalid[['Source row', 'Resident Name', 'Assessment Type', 'Period', 'Audit flags']], hide_index=True)
        with st.expander('Review excluded or invalid evaluation details'):
            st.caption('Source evidence only. Missing dates and identities stay outside current-period rankings.')
            st.dataframe(invalid[['Source row', 'Resident Name', 'Assessor original', 'Assessment Type', 'Period', 'Raw Overall'] + DOMAINS + ['Remarks', 'Audit flags']], hide_index=True, width='stretch')
            for _, record in invalid.iterrows():
                st.write(f"Row {record['Source row']} · {record['Resident Name']}")
                st.text(record['Remarks'] or 'No matched or inline remarks available.')

if len(comments) and not comments['Remarks'].str.strip().ne('').any():
    st.warning('Qualitative rows were loaded but no narrative text was found. Check the original Excel comment headers and cells. No comments have been invented or inferred.')
    st.caption('Detected narrative source: ' + ', '.join(comments['Remarks source'].unique()))

individual, ranking = st.tabs(['📊 Individual SR', '🏆 Overall Ranking'])
with individual:
    resident_catalog = pd.concat([scores[['Resident key', 'Resident Name']], comments[['Resident key', 'Resident Name']]], ignore_index=True)
    if not resident_catalog['Resident key'].ne('').any():
        st.info('No resident identities were found in either sheet.')
    else:
        keys = resident_catalog.loc[resident_catalog['Resident key'].ne('')].drop_duplicates('Resident key')
        names = dict(zip(keys['Resident key'], keys['Resident Name']))
        selected = st.selectbox('Choose resident', list(names), format_func=names.get)
        data = scenario_current[scenario_current['Resident key'].eq(selected)].copy()
        st.caption(f'Score mapping: {gm_scenario}. Individual SR shows all evaluations for the selected period; manual assessment exclusions affect the ranking scenario only.')
        if gm_scenario == 'ID-only':
            st.caption('GM evaluations and comments remain visible, but their scores and domain values are not used in this view.')
        if data.empty:
            st.info('No quantitative evaluations for this resident in the selected appraisal period. Available source comments are shown below, independently of score matching.')
        median = data['Evaluation score'].median() if data['Evaluation score'].notna().any() else float('nan')
        data['Delta vs resident median'] = data['Evaluation score'] - median
        x, y, z = st.columns(3)
        x.metric('ID-only mean (1–5)' if gm_scenario == 'ID-only' else 'Combined mean (1–5)', f"{data['Evaluation score'].mean():.2f}" if data['Evaluation score'].notna().any() else 'Not scored')
        y.metric('Median (1–5)', f'{median:.2f}' if pd.notna(median) else 'Not scored')
        z.metric('Evaluations / unique assessors', f"{len(data)} / {data.loc[data['Assessor key'].ne(''), 'Assessor key'].nunique()}")
        st.caption(f'{int(data["Evaluation score"].notna().sum())} of {len(data)} evaluations contribute a valid Overall under {gm_scenario}.')
        st.caption('A deviation from this resident’s period median describes disagreement. It does not establish assessor leniency or justify an adjustment.')
        st.subheader('Assessment profile')
        profile_month = st.selectbox('Profile month', ['All selected months'] + sorted(data['Period'].dt.strftime('%Y-%m').unique()))
        profile_data = data if profile_month == 'All selected months' else data[data['Period'].dt.strftime('%Y-%m').eq(profile_month)]
        st.caption('Each line is one evaluation, not an assessor average. Repeated assessments remain separate; missing domains leave gaps. Scores follow the active mapping; withheld GM domains leave gaps.')
        if profile_data[DOMAINS].notna().any().any():
            choices = profile_chart_options(profile_data)
            spotlight = ()
            if len(choices) >= 2:
                spotlight = st.multiselect(
                    'Spotlight assessors (chart only)', options=list(choices), format_func=choices.get,
                    max_selections=3, placeholder='All evaluations shown by default',
                    help='Choose up to three assessors. Clear your selection to show all evaluations. '
                         'This does not change the scores, table or comments.',
                    key=f'profile_spotlight_{dataset_key}_{selected}_{start}_{end}_{profile_month}_{gm_scenario}')
            if spotlight:
                st.caption('Spotlight active. Clear the selection to show all evaluations.')
            st.plotly_chart(profile_figure(
                profile_data, styles=assessor_chart_styles(scores), spotlight=spotlight,
                evaluation_dashes=assessment_chart_dashes(scores)),
                width='stretch', key='assessment_profiles')
        else:
            st.info('No valid domain scores are available for this resident.')
        st.subheader('Average domain scores')
        st.caption('Domain averages follow the profile-month filter; the period-level metrics and ranking above do not change.')
        st.dataframe(domain_summary(profile_data), hide_index=True, width='stretch',
                     column_config={'Mean (1–5)': st.column_config.NumberColumn(format='%.2f')})
        with st.expander('Optional: temporal trends', expanded=False):
            st.caption('Monthly domain means within the selected appraisal period. Counts vary by domain; unobserved months leave gaps. This descriptive view does not curve scores or add a velocity ranking.')
            if data[DOMAINS].notna().any().any():
                st.plotly_chart(temporal_figure(data), width='stretch', key='temporal_trends')
            else:
                st.info('No valid scores are available for a temporal chart.')
        st.subheader('Scores and assessment context')
        cols = ['Source row', 'Period', 'Assessment Type', 'Assessor original', 'Raw Overall', 'Evaluation score',
                'Domain mean', 'Delta vs resident median', 'Rated domains', 'Comment match', 'Remarks', 'Audit flags']
        st.dataframe(data[cols], hide_index=True, width='stretch',
                     column_config={'Remarks': st.column_config.TextColumn(width='large'),
                                    'Delta vs resident median': st.column_config.NumberColumn(format='%+.2f'),
                                    'Evaluation score': st.column_config.NumberColumn(format='%.2f'),
                                    'Domain mean': st.column_config.NumberColumn(format='%.2f')})
        st.subheader('Verbatim narrative review')
        st.caption('Original comments, ordered by date where available. All comments for this resident remain visible.')
        narratives = resident_narratives(scores, comments, selected, start if periods else None, end if periods else None)
        if narratives.empty:
            st.info('No source narrative records were found for this resident. Check the Qualitative sheet and import diagnostics.')
        uncertain_dates = int(narratives['Period'].isna().sum())
        if uncertain_dates:
            st.caption(f'{uncertain_dates} comment(s) have no confirmed year/date. The original month is shown when supplied; no year is inferred.')
        for _, row in narratives.iterrows():
            with st.expander(f"{narrative_date_label(row)} · {row['Assessor'] or 'Assessor not provided'}", expanded=True):
                st.text(row['Remarks'] or 'No comment entered.')
        with st.expander('Comment details', expanded=False):
            st.caption('Comments are not linked to scores by resident alone. Missing years are not inferred from other records. Technical matching details are retained here for audit.')
            st.dataframe(narratives[['Source','Source row','Source month','Period','Assessor','Assessment Type','Date provenance','Match status','Period context']], hide_index=True, width='stretch')
        if previous:
            try:
                prior, _ = load_workbook(previous.getvalue())
                prior = apply_gm_scenario(prior, gm_scenario)
                shared = set(prior['Resident key']) & set(current['Resident key']) - {''}
                prior_shared = prior[prior['Resident key'].isin(shared)]
                current_shared = scenario_current[scenario_current['Resident key'].isin(shared)]
                st.subheader('Prior-posting comparison: shared residents only')
                st.caption('Separate descriptive evidence, never included in current-period rank. Different posting and time contexts still matter.')
                if selected in shared:
                    comparison = pd.concat([prior_shared[prior_shared['Resident key'].eq(selected)].assign(Dataset='Prior'),
                                            current_shared[current_shared['Resident key'].eq(selected)].assign(Dataset='Current')])
                    st.dataframe(comparison.groupby(['Dataset', 'Assessor key'], as_index=False).agg(
                        Mean=('Evaluation score', 'mean'), Evaluations=('Evaluation score', 'count')), hide_index=True)
                else:
                    st.info('This resident is not shared across the two workbooks.')
            except Exception:
                st.warning('Prior workbook could not be parsed. Current-period results are unchanged.')
with ranking:
    exclusion_key = f"excluded_{dataset_key}_{start if periods else 'none'}_{end if periods else 'none'}"
    st.subheader('Assessment selection: sensitivity analysis')
    st.caption('Default: include every current-period evaluation. Exclusions are a temporary scenario in this session only. No rows are deleted, and narrative audit flags never exclude rows. The selected score scenario may leave GM values unscored, with counts shown below; the Individual SR tab uses the same mapping but keeps all evaluations visible. Changing workbook or appraisal period resets the selection.')
    choices = {int(r['Row ID']): f"Row {r['Source row']} | {r['Resident Name']} | {r['Period']:%b %Y} | {r['Assessor original']} | {r['Assessment Type']} | baseline score {r['Evaluation score']:.2f}" for _, r in current.iterrows()}
    def clear_exclusions():
        st.session_state[exclusion_key] = []
    st.button('Restore all assessments', on_click=clear_exclusions)
    excluded_ids = st.multiselect('Exclude assessments from the ranking scenario', list(choices),
                                 format_func=choices.get, key=exclusion_key)
    scenario_data = scenario_current
    included, excluded, baseline, summary, comparison = sensitivity_analysis(scenario_data, excluded_ids, baseline_frame=current)
    a, b, c = st.columns(3)
    a.metric('Baseline evaluations', len(current))
    b.metric('Included in scenario', len(included))
    c.metric('Excluded in scenario', len(excluded))
    if len(excluded):
        st.warning(f'Sensitivity scenario active: {len(excluded)} evaluations excluded, including {int(excluded["Evaluation score"].notna().sum())} with valid scenario scores. This is not a change to the baseline appraisal record.')
        st.dataframe(excluded[['Source row','Resident Name','Period','Assessor original','Assessment Type','Evaluation score']], hide_index=True, width='stretch')
    if len(excluded) or gm_scenario != 'Loose GM mapping':
        st.subheader('Unchanged baseline versus selected score scenario')
        st.dataframe(comparison, hide_index=True, width='stretch')
        with st.expander('Unchanged baseline ranking'):
            st.dataframe(baseline[['Rank','Resident Name','Combined Mean (1–5)','Median (1–5)','Total evals']], hide_index=True, width='stretch')
        st.subheader(f'Ranking: {gm_scenario}, selected assessments')
    else:
        st.caption('No exclusions and Loose mapping: the chart and ranking below are the complete current-period baseline.')
    if summary.empty:
        st.info('No eligible records in this period.')
    else:
        if summary['Combined Mean (1–5)'].notna().any():
            chart = comparison_figure(summary)
            chart.update_layout(yaxis_title='ID-only mean (1–5)' if gm_scenario == 'ID-only' else 'Scenario mean (1–5)')
            st.plotly_chart(chart, width='stretch', key='overall_comparison')
            st.caption('Bars and the tables below use the selected score scenario and the same manually included assessments. They show evaluation-weighted means, not certainty or a complete merit score. Hover for evidence counts and range; review the separate ID/GM breakdown below.')
        if not summary['Combined Mean (1–5)'].notna().any():
            st.info('No valid scored assessments remain in this scenario. Residents are shown unranked; restore assessments to recover the baseline.')
        columns = ['Rank', 'Resident Name', 'Combined Mean (1–5)', 'Median (1–5)', 'Evaluation range',
                   'ID evals', 'GM evals', 'Valid scored evals', 'Unique assessors']
        score_label = 'ID-only Mean (1–5)' if gm_scenario == 'ID-only' else 'Combined Mean (1–5)'
        st.dataframe(summary[columns].rename(columns={'Combined Mean (1–5)': score_label}), hide_index=True, width='stretch',
                     column_config={c: st.column_config.NumberColumn(format='%.2f') for c in [score_label, 'Median (1–5)']})
        st.subheader('Instrument mix and evidence coverage')
        st.dataframe(summary[['Resident Name', 'ID mean (1–5)', 'GM mean (original 1–9)', 'GM mean (mapped 1–5)',
                              'Total evals', 'Valid scored evals', 'Domain coverage']], hide_index=True)
        st.caption('ID/GM evaluation counts include forms with a missing Overall; Valid scored evals is the actual mean denominator. No inferred score is assigned to unobserved domains. In ID-only mode, GM forms remain visible in source counts but contribute no mapped score or domain values.')
