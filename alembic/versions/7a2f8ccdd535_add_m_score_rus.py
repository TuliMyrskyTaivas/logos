"""add_m_score_rus

Revision ID: 7a2f8ccdd535
Revises: 9e89b84602be
Create Date: 2026-08-16 16:28:29.068411

"""
import logging
from typing import Any, Sequence, Union, cast

import pandas as pd
from ratios import Ratios
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2f8ccdd535'
down_revision: Union[str, Sequence[str], None] = '9e89b84602be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    ratios_table = sa.table('ratios',
            sa.column('id', sa.Integer),
            sa.column('code', sa.String),
            sa.column('name', sa.String),
            sa.column('formula', sa.String),
            schema='logos'
    )
    op.bulk_insert(ratios_table, [
        {'id': 15, 'code': 'm_score_rus', 'name': 'M-Score RUS',
         'formula': 'Summary indicator Beneish M-Score (russian version)'}
    ])

    # Calculate russian version of M-Score for all companies present in the database
    bind = op.get_bind()

    ratio_id = bind.execute(
        sa.select(ratios_table.c.id).where(ratios_table.c.code == 'm_score_rus')
    ).scalar_one()

    # Metric codes required to compute M-Score RUS components:
    # dsri, gmi, aqi, sgi, sgai and lvgi (see Ratios.m_score_rus).
    required_metric_codes = [
        'accounts_receivable', 'revenue', 'gross_profit', 'fixed_assets',
        'current_assets', 'non_current_assets', 'sga',
        'long_term_liabilities', 'current_liabilities', 'total_equity',
    ]

    raw_financials = sa.table(
        'raw_financials',
        sa.column('company_id', sa.Integer),
        sa.column('period_id', sa.Integer),
        sa.column('metric_id', sa.Integer),
        sa.column('value', sa.Numeric),
        schema='logos',
    )
    fiscal_periods = sa.table(
        'fiscal_periods',
        sa.column('id', sa.Integer),
        sa.column('end_date', sa.Date),
        schema='logos',
    )
    metrics = sa.table(
        'metrics',
        sa.column('id', sa.Integer),
        sa.column('code', sa.String),
        schema='logos',
    )

    rows = bind.execute(
        sa.select(
            raw_financials.c.company_id,
            raw_financials.c.period_id,
            fiscal_periods.c.end_date,
            metrics.c.code.label('metric_code'),
            raw_financials.c.value,
        )
        .select_from(
            raw_financials
            .join(fiscal_periods, fiscal_periods.c.id == raw_financials.c.period_id)
            .join(metrics, metrics.c.id == raw_financials.c.metric_id)
        )
        .where(metrics.c.code.in_(required_metric_codes))
        .order_by(raw_financials.c.company_id, fiscal_periods.c.end_date)
    ).fetchall()

    if not rows:
        return

    df = pd.DataFrame(
        [tuple(row) for row in rows],
        columns=['company_id', 'period_id', 'end_date', 'metric_code', 'value'],
    )

    logger: logging.Logger = logging.getLogger('alembic.migration')
    calculator = Ratios(logger)

    ratio_financials = sa.table(
        'ratio_financials',
        sa.column('company_id', sa.Integer),
        sa.column('period_id', sa.Integer),
        sa.column('ratio_id', sa.Integer),
        sa.column('value', sa.Numeric),
        schema='logos',
    )

    records: list[dict[str, int | float]] = []

    for company_id, company_rows in df.groupby('company_id'):
        dates = sorted(company_rows['end_date'].unique())
        period_by_date = (
            company_rows[['end_date', 'period_id']]
            .drop_duplicates()
            .set_index('end_date')['period_id']
            .to_dict()
        )

        data: dict[str, pd.Series | None] = {}
        for code in required_metric_codes:
            metric_rows = company_rows[company_rows['metric_code'] == code]
            if metric_rows.empty:
                data[code] = None
                continue
            series = metric_rows.set_index('end_date')['value'].astype(float)
            series = series[~series.index.duplicated(keep='first')]
            data[code] = series.reindex(dates).sort_index()

        dsri = calculator.dsri(data)
        gmi = calculator.gmi(data)
        aqi = calculator.aqi(data)
        sgi = calculator.sgi(data)
        sgai = calculator.sgai(data)
        leverage = calculator.leverage(data)
        lvgi = calculator.lvgi(leverage) if leverage is not None else None

        m_score_rus = calculator.m_score_rus(dsri, gmi, aqi, sgi, sgai, lvgi)

        if not isinstance(m_score_rus, pd.Series):
            continue

        for end_date, value in m_score_rus.items():
            if pd.isna(value):
                continue
            period_id = period_by_date.get(end_date)
            if period_id is None:
                continue

            logger.info(f"Add M-Score RUS for company_id={company_id} period_id={period_id}")
            records.append({
                'company_id': int(cast(Any, company_id)),
                'period_id': int(period_id),
                'ratio_id': int(ratio_id),
                'value': float(value),
            })

    if records:
        op.bulk_insert(ratio_financials, records)

def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE from logos.ratio_financials WHERE ratio_id=15")
    op.execute("DELETE FROM logos.ratios WHERE id=15")
    pass
