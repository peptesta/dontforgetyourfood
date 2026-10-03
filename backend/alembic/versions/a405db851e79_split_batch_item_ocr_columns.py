"""split batch item ocr columns per lato (titolo/data)

Revision ID: a405db851e79
Revises: 64a24dedd198
Create Date: 2026-09-22 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a405db851e79'
down_revision: Union[str, None] = '64a24dedd198'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('batch_items', sa.Column('nome_suggerito', sa.String(length=255), nullable=True))
    op.add_column('batch_items', sa.Column('ocr_raw_text_titolo', sa.Text(), nullable=True))
    op.add_column('batch_items', sa.Column('ocr_raw_text_data', sa.Text(), nullable=True))
    op.add_column('batch_items', sa.Column('confidence_titolo', sa.Float(), nullable=True))
    op.add_column('batch_items', sa.Column('confidence_data', sa.Float(), nullable=True))
    op.add_column('batch_items', sa.Column('errore_titolo', sa.Text(), nullable=True))
    op.add_column('batch_items', sa.Column('errore_data', sa.Text(), nullable=True))

    # backfill best-effort: i dati vecchi (un solo pass OCR su foto intera) vengono
    # trattati come "lato titolo", che è il campo che più li rispecchiava.
    op.execute(
        "UPDATE batch_items SET ocr_raw_text_titolo = ocr_raw_text, "
        "confidence_titolo = confidence, errore_titolo = errore"
    )

    op.drop_column('batch_items', 'ocr_raw_text')
    op.drop_column('batch_items', 'confidence')
    op.drop_column('batch_items', 'errore')

    op.alter_column('batches', 'totale_immagini', new_column_name='totale_prodotti')


def downgrade() -> None:
    op.alter_column('batches', 'totale_prodotti', new_column_name='totale_immagini')

    op.add_column('batch_items', sa.Column('errore', sa.Text(), nullable=True))
    op.add_column('batch_items', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('batch_items', sa.Column('ocr_raw_text', sa.Text(), nullable=True))

    op.execute(
        "UPDATE batch_items SET ocr_raw_text = ocr_raw_text_titolo, "
        "confidence = confidence_titolo, errore = errore_titolo"
    )

    op.drop_column('batch_items', 'errore_data')
    op.drop_column('batch_items', 'confidence_data')
    op.drop_column('batch_items', 'ocr_raw_text_data')
    op.drop_column('batch_items', 'errore_titolo')
    op.drop_column('batch_items', 'confidence_titolo')
    op.drop_column('batch_items', 'ocr_raw_text_titolo')
    op.drop_column('batch_items', 'nome_suggerito')
