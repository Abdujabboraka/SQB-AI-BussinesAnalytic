# Hand-written migration: add service-based businesses to category choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_mcc_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='businessanalysisrequest',
            name='business_category_type',
            field=models.CharField(
                choices=[
                    ('hotel', 'Mehmonxona / Turizm'),
                    ('construction', 'Qurilish'),
                    ('textile', 'Tekstil sanoati'),
                    ('trade', 'Savdo / Chakana'),
                    ('services', "Xizmat ko'rsatish servislar(i)"),
                ],
                default='hotel',
                max_length=20,
                verbose_name='Biznes kategoriyasi turi',
            ),
        ),
    ]
