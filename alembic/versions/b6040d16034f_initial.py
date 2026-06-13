"""initial schema and data

Revision ID: 0001
Revises:
Create Date: 2025-03-15 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Создание таблиц
    op.create_table('industries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['industries.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_table('fiscal_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=True),
        sa.Column('period_type', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('end_date')
    )
    op.create_table('metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_table('ratios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('formula', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_table('companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('inn', sa.String(), nullable=True),
        sa.Column('industry_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['industry_id'], ['industries.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('raw_financials',
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Numeric(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ),
        sa.ForeignKeyConstraint(['period_id'], ['fiscal_periods.id'], ),
        sa.PrimaryKeyConstraint('company_id', 'period_id', 'metric_id')
    )
    op.create_index('idx_raw_fin_period_metric', 'raw_financials', ['period_id', 'metric_id'])
    op.create_index('idx_raw_fin_company_period', 'raw_financials', ['company_id', 'period_id'])
    op.create_table('ratio_financials',
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=False),
        sa.Column('ratio_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['period_id'], ['fiscal_periods.id'], ),
        sa.ForeignKeyConstraint(['ratio_id'], ['ratios.id'], ),
        sa.PrimaryKeyConstraint('company_id', 'period_id', 'ratio_id')
    )
    op.create_index('idx_ratio_ratio_company_period', 'ratio_financials', ['ratio_id', 'company_id', 'period_id'])

    # 2. Заполнение словарей
    # --- Отрасли ---
    industries_table = sa.table('industries',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('code', sa.String),
        sa.column('parent_id', sa.Integer)
    )
    op.bulk_insert(industries_table, [
        {'id': 1, 'name': 'Нефтегазовый сектор', 'code': 'OIL_GAS', 'parent_id': None},
        {'id': 2, 'name': 'Интегрированные нефтегазовые компании', 'code': 'OIL_INTEGRATED', 'parent_id': 1},
        {'id': 3, 'name': 'Нефтедобыча', 'code': 'OIL_UPSTREAM', 'parent_id': 1},
        {'id': 4, 'name': 'Нефтесервис', 'code': 'OIL_SERVICES', 'parent_id': 1},
        {'id': 5, 'name': 'Нефтепереработка', 'code': 'OIL_REFINING', 'parent_id': 1},
        {'id': 6, 'name': 'IT-сектор', 'code': 'IT', 'parent_id': None},
        {'id': 7, 'name': 'Разработка программного обеспечения', 'code': 'IT_SOFTWARE', 'parent_id': 6},
        {'id': 8, 'name': 'Интернет-компании', 'code': 'IT_INTERNET', 'parent_id': 6},
        {'id': 9, 'name': 'Производство оборудования', 'code': 'IT_HARDWARE', 'parent_id': 6},
        {'id': 10, 'name': 'Финансовый сектор', 'code': 'FINANCE', 'parent_id': None},
        {'id': 11, 'name': 'Банки', 'code': 'FINANCE_BANKS', 'parent_id': 10},
        {'id': 12, 'name': 'Страховые компании', 'code': 'FINANCE_INSURANCE', 'parent_id': 10},
        {'id': 13, 'name': 'Инвестиционные компании', 'code': 'FINANCE_INVESTMENT', 'parent_id': 10},
        {'id': 14, 'name': 'Пищевая промышленность', 'code': 'FOOD', 'parent_id': None},
        {'id': 15, 'name': 'Производство напитков', 'code': 'FOOD_BEVERAGES', 'parent_id': 14},
        {'id': 16, 'name': 'Производство продуктов питания', 'code': 'FOOD_PRODUCTS', 'parent_id': 14},
        {'id': 17, 'name': 'Здаровоохранение', 'code': 'HEALTHCARE', 'parent_id': None},
        {'id': 18, 'name': 'Медицинские услуги', 'code': 'HEALTHCARE_SERVICES', 'parent_id': 17},
        {'id': 19, 'name': 'Электроэнергетика', 'code': 'ENERGY', 'parent_id': None},
        {'id': 20, 'name': 'Коммунальные услуги', 'code': 'ENERGY_PRODUCTION', 'parent_id': 19},
        {'id': 21, 'name': 'Химическая промышленность', 'code': 'CHEMICAL', 'parent_id': None},
        {'id': 22, 'name': 'Производство минеральных удобрений', 'code': 'CHEMICAL_FERTILIZERS', 'parent_id': 21}
    ])

    # --- Метрики МСФО ---
    metrics_table = sa.table('metrics',
        sa.column('id', sa.Integer),
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('category', sa.String)
    )
    op.bulk_insert(metrics_table, [
        # ОПУ
        {'id': 1, 'code': 'revenue', 'name': 'Выручка', 'category': 'P&L'},
        {'id': 2, 'code': 'cogs', 'name': 'Себестоимость', 'category': 'P&L'},
        {'id': 3, 'code': 'gross_profit', 'name': 'Валовая прибыль', 'category': 'P&L'},
        {'id': 4, 'code': 'sga', 'name': 'Общехоз. и админ. расходы', 'category': 'P&L'},
        {'id': 5, 'code': 'depreciation', 'name': 'Амортизация', 'category': 'P&L'},
        {'id': 6, 'code': 'operating_profit', 'name': 'Операционная прибыль', 'category': 'P&L'},
        {'id': 7, 'code': 'interest_expense', 'name': 'Процентные расходы', 'category': 'P&L'},
        {'id': 8, 'code': 'pretax_profit', 'name': 'Прибыль до налогообложения', 'category': 'P&L'},
        {'id': 9, 'code': 'net_profit', 'name': 'Чистая прибыль', 'category': 'P&L'},
        # Баланс
        {'id': 10, 'code': 'non_current_assets', 'name': 'Внеоборотные активы', 'category': 'BS'},
        {'id': 11, 'code': 'fixed_assets', 'name': 'Основные средства', 'category': 'BS'},
        {'id': 12, 'code': 'current_assets', 'name': 'Оборотные активы', 'category': 'BS'},
        {'id': 13, 'code': 'accounts_receivable', 'name': 'Дебиторская задолженность', 'category': 'BS'},
        {'id': 14, 'code': 'total_equity', 'name': 'Общий капитал', 'category': 'BS'},
        {'id': 15, 'code': 'current_liabilities', 'name': 'Краткосрочные обязательства', 'category': 'BS'},
        {'id': 16, 'code': 'long_term_liabilities', 'name': 'Долгосрочные обязательства', 'category': 'BS'},
        # ДДС
        {'id': 17, 'code': 'cfo', 'name': 'Чистый опер. ден. поток', 'category': 'CF'},
        {'id': 18, 'code': 'cff', 'name': 'Чистый фин. ден. поток', 'category': 'CF'},
        {'id': 19, 'code': 'cfi', 'name': 'Чистый инвест. ден. поток', 'category': 'CF'},
    ])

    # --- Коэффициенты ---
    ratios_table = sa.table('ratios',
        sa.column('id', sa.Integer),
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('formula', sa.String)
    )
    op.bulk_insert(ratios_table, [
        {'id': 1, 'code': 'current_ratio', 'name': 'Current Ratio',
         'formula': 'current_assets / short_term_liabilities'},
        {'id': 2, 'code': 'leverage', 'name': 'Leverage',
         'formula': '(short_term_liabilities + long_term_liabilities) / total_equity'},
        {'id': 3, 'code': 'icr', 'name': 'Interest Coverage Ratio',
         'formula': 'operating_profit / interest_expense'},
        {'id': 4, 'code': 'rofa', 'name': 'Return on Fixed Assets',
         'formula': 'net_profit / fixed_assets'},
        {'id': 5, 'code': 'fat', 'name': 'Fixed Assets Turnover',
         'formula': 'revenue / fixed_assets'},
        # M-Score components
        {'id': 6, 'code': 'tata', 'name': 'Total Accruals to Total Assets',
         'formula': '(net_profit - cfo) / non_current_assets'},
        {'id': 7, 'code': 'aqi', 'name': 'Asset Quality Index',
         'formula': '(current_assets - accounts_receivable) / total_equity'},
        {'id': 8, 'code': 'gmi', 'name': 'Gross Margin Index',
         'formula': '(gross_profit / revenue) / (gross_profit(-1) / revenue(-1))'},
        {'id': 9, 'code': 'sgai', 'name': 'SGA Index',
         'formula': '(selling_general_administrative_expenses / revenue) / (selling_general_administrative_expenses(-1) / revenue(-1))'},
        {'id': 10, 'code': 'depi', 'name': 'Depreciation Index',
         'formula': '(depreciation_amortization / net_fixed_assets) / (depreciation_amortization(-1) / net_fixed_assets(-1))'},
        {'id': 11, 'code': 'dsri', 'name': 'Days Sales in Receivables Index',
         'formula': '(accounts_receivable / revenue) / (accounts_receivable(-1) / revenue(-1))'},
        {'id': 12, 'code': 'sgi', 'name': 'Sales Growth Index',
         'formula': '(revenue / revenue(-1)) - 1'},
        {'id': 13, 'code': 'm_score', 'name': 'M-Score',
         'formula': 'Summary indicator Beneish M-Score'},
    ])

def downgrade() -> None:
    op.drop_index('idx_ratio_ratio_company_period', table_name='ratio_financials')
    op.drop_table('ratio_financials')
    op.drop_index('idx_raw_fin_company_period', table_name='raw_financials')
    op.drop_index('idx_raw_fin_period_metric', table_name='raw_financials')
    op.drop_table('raw_financials')
    op.drop_table('companies')
    op.drop_table('ratios')
    op.drop_table('metrics')
    op.drop_table('fiscal_periods')
    op.drop_table('industries')