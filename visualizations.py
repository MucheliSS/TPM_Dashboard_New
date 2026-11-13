"""Read-only visual summaries. Charts never alter appraisal calculations."""
import pandas as pd
import plotly.express as px
from appraisal import DOMAINS


def profile_figure(data):
    data = data.copy()
    data['Assessment profile'] = data.apply(
        lambda r: f"{r['Assessor original'] or 'Assessor unavailable'} · {r['Period']:%b %Y} · row {r['Source row']}", axis=1)
    long = data.melt(id_vars=['Assessment profile', 'Assessment Type', 'Source row'],
                     value_vars=DOMAINS, var_name='Domain', value_name='Score')
    fig = px.line(long, x='Domain', y='Score', color='Assessment profile', markers=True,
                  category_orders={'Domain': DOMAINS}, hover_data=['Assessment Type', 'Source row'])
    # Retain N.A points in each trace, leaving a gap rather than implying an observed score.
    fig.update_traces(connectgaps=False)
    fig.update_layout(yaxis=dict(range=[0.8, 5.2], title='Mapped score (1–5)'),
                      xaxis_title='EPA domain', legend_title_text='Assessment', margin=dict(l=20,r=20,t=20,b=20))
    return fig


def domain_summary(data):
    return pd.DataFrame({'Domain': DOMAINS,
                         'Mean (1–5)': data[DOMAINS].mean().values,
                         'Rated evaluations': data[DOMAINS].count().values,
                         'Total evaluations': len(data)})


def temporal_figure(data):
    valid = data[data['Period'].notna()]
    long = valid.melt(id_vars=['Period'], value_vars=DOMAINS, var_name='Domain', value_name='Score')
    monthly = long.groupby(['Period', 'Domain'], as_index=False).agg(
        Mean=('Score','mean'), Rated_evaluations=('Score','count'))
    # Insert absent calendar months so the chart never bridges an unobserved interval.
    if not monthly.empty:
        grid = pd.MultiIndex.from_product([pd.date_range(valid['Period'].min(), valid['Period'].max(), freq='MS'), DOMAINS], names=['Period','Domain'])
        monthly = monthly.set_index(['Period','Domain']).reindex(grid).reset_index()
    fig = px.line(monthly, x='Period', y='Mean', color='Domain', markers=True,
                  category_orders={'Domain':DOMAINS}, hover_data=['Rated_evaluations'])
    fig.update_traces(connectgaps=False)
    fig.update_layout(yaxis=dict(range=[0.8,5.2],title='Mean mapped score (1–5)'), xaxis_title='Assessment month',
                      xaxis=dict(dtick='M1',tickformat='%b %Y'), margin=dict(l=20,r=20,t=20,b=20))
    return fig


def comparison_figure(summary):
    ranked = summary[summary['Combined Mean (1–5)'].notna()].copy()
    fig = px.bar(ranked, x='Resident Name', y='Combined Mean (1–5)',
                 hover_data=['Median (1–5)', 'Evaluation range', 'Valid scored evals', 'Unique assessors', 'ID evals', 'GM evals'],
                 text='Combined Mean (1–5)', category_orders={'Resident Name':ranked['Resident Name'].tolist()})
    # Zero baseline avoids exaggerating small mean differences with truncated bars.
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside', marker_color='#326A9E')
    fig.update_layout(yaxis=dict(range=[0,5.4],title='Combined mean (mapped 1–5)'), xaxis_title='',
                      margin=dict(l=20,r=20,t=20,b=20))
    return fig


def filter_comments(frame, residents=(), assessors=(), months=(), query=''):
    result = frame.copy()
    if residents:
        result = result[result['Resident key'].isin(residents)]
    if assessors:
        result = result[result['Assessor key'].isin(assessors)]
    if months:
        result = result[result['Period'].dt.strftime('%Y-%m').fillna('Unknown month').isin(months)]
    if query.strip():
        result = result[result['Remarks'].str.contains(query.strip(), case=False, regex=False, na=False)]
    return result
