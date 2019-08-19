"""serial_name_is_unique

Revision ID: a3d043a089fb
Revises: 3fc0a8b9bb02
Create Date: 2019-08-19 12:06:15.248114

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3d043a089fb'
down_revision = '3fc0a8b9bb02'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('serial', schema=None) as batch_op:
        batch_op.create_unique_constraint('serial_unique_constraint', ['name'])


def downgrade():
    with op.batch_alter_table('serial', schema=None) as batch_op:
        batch_op.drop_constraint('serial_unique_constraint', type_='unique')
