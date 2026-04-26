# Hand-written migration: trim MCC_CHOICES (drop 5571 Avtomobil ehtiyot qismlari)
# Existing rows with mcc_code='5571' (if any) remain readable but won't appear in dropdowns.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_businessanalysisrequest_is_24_7_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='businessanalysisrequest',
            name='mcc_code',
            field=models.CharField(
                choices=[
                    ('5812', 'Restoran / Kafe'),
                    ('5411', "Oziq-ovqat do'koni / Supermarket"),
                    ('5912', 'Dorixona / Apteka'),
                    ('5661', "Kiyim-kechak do'koni"),
                    ('7011', 'Mehmonxona / Hotel'),
                    ('5251', "Qurilish mollari do'koni"),
                    ('8099', 'Tibbiy xizmatlar'),
                    ('7299', "Maishiy xizmatlar (sartaroshxona, go'zallik saloni)"),
                    ('5999', 'Boshqa chakana savdo'),
                ],
                max_length=10,
                verbose_name='MCC Kategoriya',
            ),
        ),
    ]
