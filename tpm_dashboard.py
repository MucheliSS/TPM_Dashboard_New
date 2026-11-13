"""Summative appraisal evidence dashboard. Run: streamlit run tpm_dashboard.py."""
from io import BytesIO
import pandas as pd
import plotly.express as px
import streamlit as st
from appraisal import (DOMAINS, INSTRUMENTS, ALIASES, prepare_quantitative, join_remarks,
                       in_period, resident_summary, synthetic_data, workbook_bytes)

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
    q, comments = synthetic_data()
    scores, comments = join_remarks(prepare_quantitative(q), comments)
    st.warning('Demonstration: all names, scores and comments below are fictional.')
    st.download_button('Download synthetic Excel template', workbook_bytes(q, synthetic_data()[1]), 'synthetic_appraisal_template.xlsx')
elif upload:
    try:
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

with st.expander('Import validation and scoring rules', expanded=True):
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

individual, narrative, ranking = st.tabs(['📊 Individual SR', '💬 Score and narrative audit', '🏆 Overall Ranking'])
with individual:
    if current.empty or not current['Resident key'].ne('').any():
        st.info('No resident evaluations in this period.')
    else:
        keys = current.loc[current['Resident key'].ne(''), ['Resident key', 'Resident Name']].drop_duplicates('Resident key')
        names = dict(zip(keys['Resident key'], keys['Resident Name']))
        selected = st.selectbox('Choose resident', list(names), format_func=names.get)
        data = current[current['Resident key'].eq(selected)].copy()
        median = data['Evaluation score'].median() if data['Evaluation score'].notna().any() else float('nan')
        data['Delta vs resident median'] = data['Evaluation score'] - median
        x, y, z = st.columns(3)
        x.metric('Combined mean (1–5)', f"{data['Evaluation score'].mean():.2f}" if data['Evaluation score'].notna().any() else 'Not scored')
        y.metric('Median (1–5)', f'{median:.2f}' if pd.notna(median) else 'Not scored')
        z.metric('Evaluations / unique assessors', f"{len(data)} / {data.loc[data['Assessor key'].ne(''), 'Assessor key'].nunique()}")
        st.caption('A deviation from this resident’s period median describes disagreement. It does not establish assessor leniency or justify an adjustment.')
        cols = ['Source row', 'Period', 'Assessment Type', 'Assessor original', 'Raw Overall', 'Evaluation score',
                'Domain mean', 'Delta vs resident median', 'Rated domains', 'Comment match', 'Remarks', 'Audit flags']
        st.dataframe(data[cols], hide_index=True, width='stretch',
                     column_config={'Remarks': st.column_config.TextColumn(width='large'),
                                    'Delta vs resident median': st.column_config.NumberColumn(format='%+.2f'),
                                    'Evaluation score': st.column_config.NumberColumn(format='%.2f'),
                                    'Domain mean': st.column_config.NumberColumn(format='%.2f')})
        st.subheader('Verbatim narrative review')
        for _, row in data.iterrows():
            with st.expander(f"Row {row['Source row']} · {row['Period']:%b %Y} · {row['Assessor original']} · {row['Assessment Type']}"):
                st.text(row['Remarks'] or 'No matched or inline remark available.')
                st.caption(row['Audit flags'] or 'No automatic flags. This does not establish evidence quality.')
                st.dataframe(pd.DataFrame({'Domain': DOMAINS, 'Mapped score': [row[d] for d in DOMAINS],
                                           'Original score': [row[f'Raw {d}'] for d in DOMAINS]}), hide_index=True)
        plot = data.melt(id_vars=['Source row', 'Period', 'Assessor original'], value_vars=DOMAINS,
                         var_name='Domain', value_name='Mapped score').dropna(subset=['Mapped score'])
        if not plot.empty:
            fig = px.scatter(plot, x='Domain', y='Mapped score', color='Assessor original', hover_data=['Source row', 'Period'], range_y=[0.8, 5.2])
            st.plotly_chart(fig, width='stretch')
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
    st.subheader('Current-period evaluation evidence')
    st.dataframe(current[['Source row', 'Resident Name', 'Period', 'Assessor original', 'Evaluation score', 'Remarks', 'Audit flags']], hide_index=True, width='stretch')
    st.subheader('Unmatched or ambiguous qualitative records')
    st.caption('Shown separately, not attributed to a scored evaluation and never used to change rankings. May include records outside the selected period.')
    unmatched = comments[comments['Match status'].ne('Matched')]
    st.dataframe(unmatched[['Source row', 'Resident Name', 'Period', 'Assessor original', 'Remarks', 'Match status']], hide_index=True, width='stretch')
with ranking:
    st.subheader('Current-period summative standing')
    st.caption('Committee decision support, not a complete measure of merit or service contribution. Small numeric differences and sparse evidence require judgement.')
    summary = resident_summary(current)
    if summary.empty:
        st.info('No eligible records in this period.')
    else:
        columns = ['Rank', 'Resident Name', 'Combined Mean (1–5)', 'Median (1–5)', 'Evaluation range',
                   'ID evals', 'GM evals', 'Valid scored evals', 'Unique assessors', 'Context / Audit Flags']
        st.dataframe(summary[columns], hide_index=True, width='stretch',
                     column_config={c: st.column_config.NumberColumn(format='%.2f') for c in ['Combined Mean (1–5)', 'Median (1–5)']})
        st.subheader('Instrument mix and evidence coverage')
        st.dataframe(summary[['Resident Name', 'ID mean (1–5)', 'GM mean (original 1–9)', 'GM mean (mapped 1–5)',
                              'Total evals', 'Valid scored evals', 'Unknown evals', 'Domain coverage', 'Flagged evals']], hide_index=True)
        st.caption('ID/GM evaluation counts include forms with a missing Overall; Valid scored evals is the actual mean denominator. No inferred score is assigned to unobserved domains.')
