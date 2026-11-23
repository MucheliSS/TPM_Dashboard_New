"""Read-only visual summaries. Charts never alter appraisal calculations."""
from html import escape

import pandas as pd
import plotly.express as px
from appraisal import DOMAINS


PROFILE_RANGE = [0.8, 5.2]
PALETTE = ('#0072B2', '#A85200', '#00805C', '#A43D79',
           '#5C3DAA', '#007C91', '#A8342C', '#4F595E')
MARKERS = ('circle', 'square', 'triangle-up', 'diamond',
           'cross', 'triangle-down', 'hexagon', 'star')
DASHES = ('solid', 'dash', 'dot', 'dashdot')


def assessor_chart_styles(data):
    """Build a style map from the whole workbook, not a filtered view."""
    assessors = sorted(set(data['Assessor key']) - {''})
    return {key: (PALETTE[i % len(PALETTE)],
                  MARKERS[(i + i // len(PALETTE)) % len(MARKERS)])
            for i, key in enumerate(assessors)}


def profile_chart_options(data):
    """Only named assessors with a visible score can be spotlighted."""
    scored = data[data[DOMAINS].notna().any(axis=1) & data['Assessor key'].ne('')]
    rows = scored.sort_values('Source row').drop_duplicates('Assessor key')
    return dict(sorted(zip(rows['Assessor key'], rows['Assessor original']),
                       key=lambda item: (item[1].casefold(), item[0])))


def readable_chart(fig):
    fig.update_layout(font_size=16, hoverlabel_font_size=16, legend_font_size=16,
                      legend_title_font_size=17,
                      margin=dict(l=20, r=25, t=20, b=20),
                      legend=dict(orientation='h', x=0, y=-0.2))
    fig.update_xaxes(tickfont_size=16, title_font_size=18, automargin=True)
    fig.update_yaxes(tickfont_size=16, title_font_size=18, automargin=True)
    return fig


def profile_figure(data, *, styles=None, spotlight=(), evaluation_dashes=None):
    styles = assessor_chart_styles(data) if styles is None else styles
    data = data.copy()
    data['Assessment profile'] = data.apply(
        lambda r: f"{r['Assessor original'] or 'Assessor unavailable'} · {r['Period']:%b %Y} · row {r['Source row']}", axis=1)
    if spotlight:
        data = data[data['Assessor key'].isin(spotlight)]
    long = data.melt(id_vars=['Assessment profile', 'Assessment Type', 'Source row'],
                     value_vars=DOMAINS, var_name='Domain', value_name='Score')
    fig = px.line(long, x='Domain', y='Score', color='Assessment profile', markers=True,
                  category_orders={'Domain': DOMAINS}, hover_data=['Assessment Type', 'Source row'])
    rows = data.set_index('Assessment profile')
    for trace in fig.data:
        row = rows.loc[trace.name]
        color, symbol = styles.get(row['Assessor key'], ('#555555', 'circle-open'))
        dash = (evaluation_dashes or {}).get(row['Source row'], 'solid')
        trace.update(connectgaps=False, line=dict(color=color, width=3, dash=dash),
                     marker=dict(symbol=symbol, size=10))
    # Leave crowded or tied endpoints to the legend and hover rather than overlaying labels.
    endpoints = [(trace, float(trace.y[-1])) for trace in fig.data
                 if len(trace.y) and pd.notna(trace.y[-1])]
    if 0 < len(fig.data) <= 4 and endpoints:
        for trace, score in endpoints:
            if any(other is not trace and abs(score - other_score) < 0.34
                   for other, other_score in endpoints):
                continue
            row = rows.loc[trace.name]
            name = row['Assessor original'] or 'Unnamed'
            name = name if len(name) <= 16 else name[:15].rstrip() + '…'
            name = escape(name)
            if data['Assessor key'].eq(row['Assessor key']).sum() > 1:
                name += f" · {row['Source row']}"
            fig.add_annotation(x=DOMAINS[-1], y=score, text=name, showarrow=False,
                               xanchor='left', xshift=10, font=dict(size=15, color=trace.line.color))
    if fig.layout.annotations:
        # The numerical category range adds space after the final scored domain.
        fig.update_xaxes(range=[-0.25, len(DOMAINS) + 0.15])
    fig.update_layout(yaxis=dict(range=PROFILE_RANGE, fixedrange=True, dtick=1,
                                 title='Mapped score (1–5)'),
                      height=510, xaxis_title='EPA domain', legend_title_text='Assessment')
    return readable_chart(fig)


def assessment_chart_dashes(data):
    """Distinguish repeat evaluations without changing the assessor's colour or shape."""
    ordered = data.sort_values('Source row')
    ordinal = ordered.groupby(['Resident key', 'Assessor key']).cumcount()
    return dict(zip(ordered['Source row'], (DASHES[i % len(DASHES)] for i in ordinal)))


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
    for i, trace in enumerate(fig.data):
        trace.update(connectgaps=False, line=dict(color=PALETTE[i], width=3),
                     marker=dict(symbol=MARKERS[i], size=9))
    fig.update_layout(yaxis=dict(range=[0.8,5.2],title='Mean mapped score (1–5)'), xaxis_title='Assessment month',
                      xaxis=dict(dtick='M1',tickformat='%b %Y'))
    return readable_chart(fig)


def comparison_figure(summary):
    ranked = summary[summary['Combined Mean (1–5)'].notna()].copy()
    fig = px.bar(ranked, x='Resident Name', y='Combined Mean (1–5)',
                 hover_data=['Median (1–5)', 'Evaluation range', 'Valid scored evals', 'Unique assessors', 'ID evals', 'GM evals'],
                 text='Combined Mean (1–5)', category_orders={'Resident Name':ranked['Resident Name'].tolist()})
    # Zero baseline avoids exaggerating small mean differences with truncated bars.
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside',
                      textfont_size=16, marker_color='#326A9E')
    fig.update_layout(yaxis=dict(range=[0,5.4],title='Combined mean (mapped 1–5)'), xaxis_title='')
    return readable_chart(fig)


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
