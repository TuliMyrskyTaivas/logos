"""add_stress_scenarios

Revision ID: 9e89b84602be
Revises: 0001
Create Date: 2026-06-21 13:50:40.411851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e89b84602be'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create scenarios table
    op.create_table('scenarios',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_unique_constraint('uq_scenarios_code', 'scenarios', ['code'])

    # Fill scenarios table
    scenarios = sa.table('scenarios',
        sa.column('id', sa.Integer),
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('category', sa.String),
        sa.column('description', sa.String)
    )
    op.bulk_insert(scenarios, [
        {'id': 1, 'code': 'mild_stress', 'name': 'Mild Stress (-10% Revenue)', 'category': 'demand_shock',
         'description': 'Moderate decline in demand: revenue -10%, cost price is scaling.'},
        {'id': 2, 'code': 'severe_stress', 'name': 'Severe Stress (-20% Rev, +20% COGS)', 'category': 'demand_shock',
         'description': 'Hard shock: revenue -20%, cost +20%.'},
        {'id': 3, 'code': 'deep_recession', 'name': 'Deep Recession (-30% Revenue)', 'category': 'demand_shock',
         'description': 'Deep recession: revenue -30%, variable costs proportional.'},
        {'id': 4, 'code': 'pandemic', 'name': 'Pandemic-style (-50% Rev, SGA -20%)', 'category': 'demand_shock',
         'description': 'Lockdown: revenue -50%, SGA only reduced by 20%.'},
        {'id': 5, 'code': 'cost_inflation', 'name': 'Cost-push Inflation (COGS +15%, SGA +10%)', 'category': 'cost_shock',
         'description': 'Cost inflation: cost price +15%, overhead +10%.'},
        {'id': 6, 'code': 'commodity_cycle', 'name': 'Commodity Super-cycle (COGS +40%)', 'category': 'cost_shock',
         'description': 'Raw material cost jump: cost price +40%.'},
        {'id': 7, 'code': 'rate_hike', 'name': 'Rate Hike (+300 bps)', 'category': 'rate_shock',
         'description': 'Increase in the Central Bank rate: interest expenses +30%.'},
        {'id': 8, 'code': 'ruble_devaluation', 'name': 'Ruble Devaluation (-25%)', 'category': 'rate_shock',
         'description': 'Ruble weakening: revenue +5%, COGS +15%, interest +25%.'},
        {'id': 9, 'code': 'liquidity_crunch', 'name': 'Liquidity Crunch (AR +50%)', 'category': 'liquidity',
         'description': 'Freezing of working capital: accounts receivable +50%, CFO falls.'},
        {'id': 10, 'code': 'perfect_storm', 'name': 'Perfect Storm (-15% Rev, +10% COGS, +20% Int)', 'category': 'combined',
         'description': 'A perfect storm: falling revenues, rising costs and rates all at the same time.'},
        {'id': 11, 'code': 'booming_demand', 'name': 'Booming Demand (+15% Revenue)', 'category': 'upside',
         'description': 'Demand boom: revenue +15%.'},
        {'id': 12, 'code': 'op_efficiency', 'name': 'Operational Efficiency (SGA -10%)', 'category': 'upside',
         'description': 'Optimization: general business expenses -10%.'}
    ])

    # Create a table for scenario variables
    op.create_table('scenario_variables',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('operator', sa.String(), nullable=False),
        sa.Column('value', sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_unique_constraint('uq_scenario_metric', 'scenario_variables', ['scenario_id', 'metric_id'])

    # Fill scenario variables
    scenario_variables = sa.table('scenario_variables',
        sa.column('scenario_id', sa.Integer),
        sa.column('metric_id', sa.Integer),
        sa.column('operator', sa.String),
        sa.column('value', sa.Numeric)
    )
    op.bulk_insert(scenario_variables, [
        # id=1 -> mild_stress,  revenue -10 %
        {'scenario_id': 1, 'metric_id': 1, 'operator': 'multiply', 'value': 0.9 },
        # id=2 -> severe_stress, revenue -20 %, cogs +20 %
        {'scenario_id': 2, 'metric_id': 1, 'operator': 'multiply', 'value': 0.8 },
        {'scenario_id': 2, 'metric_id': 2, 'operator': 'multiply', 'value': 1.2 },
        # id=3 -> deep_recession, revenue -30%, cogs +30%, sga +10%, depreciation +10%
        {'scenario_id': 3, 'metric_id': 1, 'operator': 'multiply', 'value': 0.7 },
        {'scenario_id': 3, 'metric_id': 2, 'operator': 'multiply', 'value': 1.3 },
        {'scenario_id': 3, 'metric_id': 4, 'operator': 'multiply', 'value': 0.7 },
        {'scenario_id': 3, 'metric_id': 5, 'operator': 'multiply', 'value': 0.7 },
        # id=4 -> pandemic, revenue -50% , sga -20%
        {'scenario_id': 4, 'metric_id': 1, 'operator': 'multiply', 'value': 0.5 },
        {'scenario_id': 4, 'metric_id': 4, 'operator': 'multiply', 'value': 0.8 },
        # id=5 -> cost_inflation, cogs +15%, sga +10%
        {'scenario_id': 5, 'metric_id': 2, 'operator': 'multiply', 'value': 1.15 },
        {'scenario_id': 5, 'metric_id': 4, 'operator': 'multiply', 'value': 1.10 },
        # id=6 -> commodity_cycle, cogs +40%
        {'scenario_id': 6, 'metric_id': 2, 'operator': 'multiply', 'value': 1.40 },
        # id=7 -> rate_hike, interest_expense +30%
        {'scenario_id': 7, 'metric_id': 7, 'operator': 'multiply', 'value': 1.30 },
        # id=8 -> ruble_devaluation, revenue +5%, cogs +15%, interest_expense +25%
        {'scenario_id': 8, 'metric_id': 1, 'operator': 'multiply', 'value': 1.05 },
        {'scenario_id': 8, 'metric_id': 2, 'operator': 'multiply', 'value': 1.15 },
        {'scenario_id': 8, 'metric_id': 7, 'operator': 'multiply', 'value': 1.25 },
        # id=9 -> liquidity_crunch, interest_expense +50%, revenue -15%
        {'scenario_id': 9, 'metric_id': 1, 'operator': 'multiply', 'value': 0.85 },
        {'scenario_id': 9, 'metric_id': 7, 'operator': 'multiply', 'value': 1.50 },
        # id=10 -> perfect_storm, revenue -15%, cogs +10%, interest_expense +20%
        {'scenario_id': 10, 'metric_id': 1, 'operator': 'multiply', 'value': 0.85 },
        {'scenario_id': 10, 'metric_id': 2, 'operator': 'multiply', 'value': 1.10 },
        {'scenario_id': 10, 'metric_id': 7, 'operator': 'multiply', 'value': 1.20 },
        # id=11 -> booming_demand, revenue +15%
        {'scenario_id': 11, 'metric_id': 1, 'operator': 'multiply', 'value': 1.15 },
        # id=12 -> op_efficiency, sga -10%
        {'scenario_id': 12, 'metric_id': 4, 'operator': 'multiply', 'value': 0.9 },
    ])

    op.create_table('forecasts',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('forecast_year', sa.Integer(), nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE')
    )
    op.create_unique_constraint('uq_forecast_company_scenario_metric', 'forecasts', ['company_id', 'scenario_id', 'forecast_year', 'metric_id'])
    op.create_index('idx_forecast_company_scenario', 'forecasts', ['company_id', 'scenario_id', 'forecast_year'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_forecast_company_scenario')
    op.drop_constraint('uq_forecast_company_scenario_metric', 'forecasts', type_='unique')
    op.drop_table('forecasts')
    op.drop_constraint('uq_scenario_metric', 'scenario_variables', type_='unique')
    op.drop_table('scenario_variables')
    op.drop_table('scenarios')
    pass
