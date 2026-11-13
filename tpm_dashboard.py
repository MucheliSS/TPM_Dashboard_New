"""Summative appraisal evidence dashboard. Run: streamlit run tpm_dashboard.py."""
from io import BytesIO
from hashlib import sha256
import pandas as pd
import streamlit as st
from appraisal import (DOMAINS, INSTRUMENTS, ALIASES, prepare_quantitative, join_remarks,
                       in_period, resident_summary, synthetic_data, workbook_bytes, resident_narratives, sensitivity_analysis)

from visualizations import profile_figure, domain_summary, temporal_figure, comparison_figure, filter_comments

st.set_page_config(page_title='SR appraisal evidence', page_icon='📊', layout='wide')
st.title('Senior Resident appraisal evidence')
st.caption('Current-period summative evidence • No seniority adjustment • No automatic bonus allocation')
st.info('Combined scores use linear GM endpoint rescaling, not proven equivalence of rating anchors. Read the ID/GM breakdown and narratives before making appraisal judgements.')


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
    st.write('GM mapping: (raw + 1) ÷ 2. Zero and N.A are unrated. Invalid scores and unknown instruments are not scored. Current-period ranking excludes missing dates and missing resident names. Flags prompt review and never deduct points.')
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

individual, narrative, ranking = st.tabs(['📊 Individual SR', '💬 Score and narrative audit', '🏆 Overall Ranking'])
with individual:
    resident_catalog = pd.concat([scores[['Resident key', 'Resident Name']], comments[['Resident key', 'Resident Name']]], ignore_index=True)
    if not resident_catalog['Resident key'].ne('').any():
        st.info('No resident identities were found in either sheet.')
    else:
        keys = resident_catalog.loc[resident_catalog['Resident key'].ne('')].drop_duplicates('Resident key')
        names = dict(zip(keys['Resident key'], keys['Resident Name']))
        selected = st.selectbox('Choose resident', list(names), format_func=names.get)
        data = current[current['Resident key'].eq(selected)].copy()
        if data.empty:
            st.info('No quantitative evaluations for this resident in the selected appraisal period. Available source comments are shown below, independently of score matching.')
        median = data['Evaluation score'].median() if data['Evaluation score'].notna().any() else float('nan')
        data['Delta vs resident median'] = data['Evaluation score'] - median
        x, y, z = st.columns(3)
        x.metric('Combined mean (1–5)', f"{data['Evaluation score'].mean():.2f}" if data['Evaluation score'].notna().any() else 'Not scored')
        y.metric('Median (1–5)', f'{median:.2f}' if pd.notna(median) else 'Not scored')
        z.metric('Evaluations / unique assessors', f"{len(data)} / {data.loc[data['Assessor key'].ne(''), 'Assessor key'].nunique()}")
        st.caption('A deviation from this resident’s period median describes disagreement. It does not establish assessor leniency or justify an adjustment.')
        st.subheader('Assessment profile')
        profile_month = st.selectbox('Profile month', ['All selected months'] + sorted(data['Period'].dt.strftime('%Y-%m').unique()))
        profile_data = data if profile_month == 'All selected months' else data[data['Period'].dt.strftime('%Y-%m').eq(profile_month)]
        st.caption('Each line is one evaluation, not an assessor average. Repeated assessments remain separate; missing domains leave gaps. GM values are linearly rescaled.')
        if profile_data[DOMAINS].notna().any().any():
            st.plotly_chart(profile_figure(profile_data), width='stretch', key='assessment_profiles')
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
        st.caption('All qualitative source comments for this resident are shown, including unmatched, ambiguous and undated records. They are not assigned to a score merely because the resident matches. The profile-month filter does not hide these narratives.')
        narratives = resident_narratives(scores, comments, selected, start if periods else None, end if periods else None)
        if narratives.empty:
            st.info('No source narrative records were found for this resident. Check the Qualitative sheet and import diagnostics.')
        for _, row in narratives.iterrows():
            date_label = row['Period'].strftime('%b %Y') if pd.notna(row['Period']) else 'Unknown date'
            with st.expander(f"{date_label} · {row['Assessor'] or 'Assessor unavailable'} · {row['Source']} row {row['Source row']}", expanded=True):
                st.caption(f"{row['Period context']} | {row['Match status']} | {row['Assessment Type'] or 'Instrument unspecified'} | Source field(s): {row['Remarks source']}")
                st.text(row['Remarks'] or 'This source row has no narrative text.')
        if previous:
            try:
                prior, _ = load_workbook(previous.getvalue())
                shared = set(prior['Resident key']) & set(current['Resident key']) - {''}
                prior_shared = prior[prior['Resident key'].isin(shared)]
                current_shared = current[current['Resident key'].isin(shared)]
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
with narrative:
    st.subheader('Filter comments')
    st.caption('Filters affect this comments tab only, not scores or ranking. Search matches literal text, not sentiment.')
    context = pd.concat([current, comments], ignore_index=True)
    resident_names = dict(zip(context['Resident key'], context['Resident Name']))
    assessor_names = dict(zip(context['Assessor key'], context['Assessor original']))
    f1, f2, f3 = st.columns(3)
    resident_filter = f1.multiselect('Residents', sorted(k for k in resident_names if k), format_func=resident_names.get)
    assessor_filter = f2.multiselect('Assessors', sorted(k for k in assessor_names if k), format_func=assessor_names.get)
    month_options = sorted(context['Period'].dt.strftime('%Y-%m').fillna('Unknown month').unique())
    month_filter = f3.multiselect('Assessment months', month_options)
    query = st.text_input('Search remarks')
    filtered = filter_comments(current, resident_filter, assessor_filter, month_filter, query)
    st.subheader('Current-period evaluation evidence')
    st.caption(f'{len(filtered)} of {len(current)} current-period evaluations shown.')
    if filtered.empty:
        st.info('No evaluation comments match these filters. Clear a filter to broaden the view.')
    st.dataframe(filtered[['Source row', 'Resident Name', 'Period', 'Assessor original', 'Evaluation score', 'Remarks', 'Audit flags']], hide_index=True, width='stretch')
    for _, row in filtered.iterrows():
        with st.expander(f"{row['Resident Name']} · {row['Period']:%b %Y} · {row['Assessor original']} · row {row['Source row']}"):
            st.text(row['Remarks'] or 'No matched or inline remark available.')
    st.subheader('Unmatched or ambiguous qualitative records')
    st.caption('Not attributed to a scored evaluation and never used to change rankings. The same comments filters apply here.')
    include_outside = st.checkbox('Include unmatched records outside the appraisal period or with unknown dates')
    unmatched = comments[comments['Match status'].ne('Matched')]
    if not include_outside:
        unmatched = in_period(unmatched, start, end) if periods else unmatched.iloc[0:0]
    unmatched = filter_comments(unmatched, resident_filter, assessor_filter, month_filter, query)
    st.dataframe(unmatched[['Source row', 'Resident Name', 'Period', 'Assessor original', 'Remarks', 'Match status']], hide_index=True, width='stretch')
    for _, row in unmatched.iterrows():
        date_label = row['Period'].strftime('%b %Y') if pd.notna(row['Period']) else 'Unknown month'
        with st.expander(f"Unmatched row {row['Source row']} · {row['Resident Name']} · {date_label} · {row['Assessor original']}"):
            st.text(row['Remarks'] or 'No remark supplied.')
            st.caption(row['Match status'])
with ranking:
    st.subheader('Current-period summative standing')
    st.caption('Committee decision support, not a complete measure of merit or service contribution. Small numeric differences and sparse evidence require judgement.')
    exclusion_key = f"excluded_{dataset_key}_{start if periods else 'none'}_{end if periods else 'none'}"
    st.subheader('Assessment selection: sensitivity analysis')
    st.caption('Default: include every current-period evaluation. Exclusions are a temporary scenario in this session only. No rows are deleted, no flags automatically exclude a row, and the individual/narrative tabs continue to show the baseline evidence. Changing workbook or appraisal period resets the selection.')
    choices = {int(r['Row ID']): f"Row {r['Source row']} | {r['Resident Name']} | {r['Period']:%b %Y} | {r['Assessor original']} | {r['Assessment Type']} | score {r['Evaluation score']:.2f}" for _, r in current.iterrows()}
    def clear_exclusions():
        st.session_state[exclusion_key] = []
    st.button('Restore all assessments', on_click=clear_exclusions)
    excluded_ids = st.multiselect('Exclude assessments from the ranking scenario', list(choices),
                                 format_func=choices.get, key=exclusion_key)
    included, excluded, baseline, summary, comparison = sensitivity_analysis(current, excluded_ids)
    a, b, c = st.columns(3)
    a.metric('Baseline evaluations', len(current))
    b.metric('Included in scenario', len(included))
    c.metric('Excluded in scenario', len(excluded))
    if len(excluded):
        st.warning(f'Sensitivity scenario active: {len(excluded)} evaluations excluded, including {int(excluded["Evaluation score"].notna().sum())} with valid scores. This is not a change to the baseline appraisal record.')
        st.dataframe(excluded[['Source row','Resident Name','Period','Assessor original','Assessment Type','Evaluation score','Audit flags']], hide_index=True, width='stretch')
        st.subheader('Baseline versus selected assessments')
        st.dataframe(comparison, hide_index=True, width='stretch')
        with st.expander('Unchanged baseline ranking'):
            st.dataframe(baseline[['Rank','Resident Name','Combined Mean (1–5)','Median (1–5)','Total evals']], hide_index=True, width='stretch')
        st.subheader('Selected-assessment scenario ranking')
    else:
        st.caption('No exclusions: the chart and ranking below are the complete current-period baseline.')
    if summary.empty:
        st.info('No eligible records in this period.')
    else:
        if summary['Combined Mean (1–5)'].notna().any():
            st.plotly_chart(comparison_figure(summary), width='stretch', key='overall_comparison')
            st.caption('Bars and the tables below use the same selected assessments. They show evaluation-weighted means, not certainty or a complete merit score. Hover for evidence counts and range; review the separate ID/GM breakdown below.')
        if not summary['Combined Mean (1–5)'].notna().any():
            st.info('No valid scored assessments remain in this scenario. Residents are shown unranked; restore assessments to recover the baseline.')
        columns = ['Rank', 'Resident Name', 'Combined Mean (1–5)', 'Median (1–5)', 'Evaluation range',
                   'ID evals', 'GM evals', 'Valid scored evals', 'Unique assessors', 'Context / Audit Flags']
        st.dataframe(summary[columns], hide_index=True, width='stretch',
                     column_config={c: st.column_config.NumberColumn(format='%.2f') for c in ['Combined Mean (1–5)', 'Median (1–5)']})
        st.subheader('Instrument mix and evidence coverage')
        st.dataframe(summary[['Resident Name', 'ID mean (1–5)', 'GM mean (original 1–9)', 'GM mean (mapped 1–5)',
                              'Total evals', 'Valid scored evals', 'Unknown evals', 'Domain coverage', 'Flagged evals']], hide_index=True)
        st.caption('ID/GM evaluation counts include forms with a missing Overall; Valid scored evals is the actual mean denominator. No inferred score is assigned to unobserved domains.')
