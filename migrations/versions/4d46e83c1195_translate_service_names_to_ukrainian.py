"""translate service names to ukrainian

Revision ID: 4d46e83c1195
Revises: a9bd2374d20f
Create Date: 2026-05-22 15:44:36.486859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d46e83c1195'
down_revision: Union[str, Sequence[str], None] = 'a9bd2374d20f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Translate service display names from English to Ukrainian."""
    translations = {
        # Vet clinic
        "vaccination": "Вакцинація",
        "surgery": "Хірургія",
        "diagnostics": "Діагностика",
        "emergency_care": "Невідкладна допомога",
        "dental": "Стоматологія",
        "ultrasound": "УЗД",
        "xray": "Рентген",
        "lab_tests": "Лабораторні аналізи",
        "microchipping": "Чіпування",
        # Grooming
        "haircut": "Стрижка",
        "bath": "Купання",
        "nail_trim": "Обрізання кігтів",
        "ear_cleaning": "Чистка вух",
        # Pet shop
        "food": "Корм",
        "accessories": "Аксесуари",
        "toys": "Іграшки",
    }
    
    for slug, name_uk in translations.items():
        op.execute(
            sa.text("UPDATE services SET name = :name WHERE slug = :slug")
            .bindparams(name=name_uk, slug=slug)
        )



def downgrade() -> None:
    """Revert service display names to English."""
    english_names = {
        # Vet clinic
        "vaccination": "Vaccination",
        "surgery": "Surgery",
        "diagnostics": "Diagnostics",
        "emergency_care": "Emergency Care",
        "dental": "Dental Care",
        "ultrasound": "Ultrasound",
        "xray": "X-Ray",
        "lab_tests": "Laboratory Tests",
        "microchipping": "Microchipping",
        # Grooming
        "haircut": "Haircut",
        "bath": "Bath & Wash",
        "nail_trim": "Nail Trimming",
        "ear_cleaning": "Ear Cleaning",
        # Pet shop
        "food": "Food",
        "accessories": "Accessories",
        "toys": "Toys",
    }

    for slug, name_en in english_names.items():
        op.execute(
            sa.text("UPDATE services SET name = :name WHERE slug = :slug")
            .bindparams(name=name_en, slug=slug)
        )
