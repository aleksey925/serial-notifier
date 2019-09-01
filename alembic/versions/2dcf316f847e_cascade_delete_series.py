"""cascade delete series

Revision ID: 2dcf316f847e
Revises: a3d043a089fb
Create Date: 2019-09-01 16:44:23.999461

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import orm


revision = '2dcf316f847e'
down_revision = 'a3d043a089fb'
branch_labels = None
depends_on = None


NEW_SERIES_TABLE_ARGS = (
    'series',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('id_serial', sa.Integer(), nullable=True),
    sa.Column('series_number', sa.Integer(), nullable=True),
    sa.Column('season_number', sa.Integer(), nullable=True),
    sa.Column('looked', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['id_serial'], ['serial.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
)

OLD_SERIES_TABLE_ARGS = (
    'series',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('id_serial', sa.Integer(), nullable=True),
    sa.Column('series_number', sa.Integer(), nullable=True),
    sa.Column('season_number', sa.Integer(), nullable=True),
    sa.Column('looked', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['id_serial'], ['serial.id'], ),
    sa.PrimaryKeyConstraint('id')
)


def move_data(table_args):
    temp_serial_table_name = 'series_temp'
    column_series_tabel = [
        'id', 'id_serial', 'series_number', 'season_number', 'looked'
    ]
    sql_get_all_series = (
        f'select {", ".join(column_series_tabel)} '
        f'from {temp_serial_table_name}'
    )

    # В sqlite нельзя изменить foreign key, по этому приходится создавать новую
    # таблицу и переносить в нее данные из старой
    op.rename_table('series', temp_serial_table_name)

    new_series_table = op.create_table(*table_args)

    bind = op.get_bind()
    session = orm.Session(bind=bind)

    all_series = list(map(
        lambda row: dict(zip(column_series_tabel, row)),
        session.execute(sql_get_all_series)
    ))
    op.bulk_insert(new_series_table, all_series)
    session.commit()

    op.drop_table(temp_serial_table_name)


def upgrade():
    move_data(NEW_SERIES_TABLE_ARGS)


def downgrade():
    move_data(OLD_SERIES_TABLE_ARGS)
