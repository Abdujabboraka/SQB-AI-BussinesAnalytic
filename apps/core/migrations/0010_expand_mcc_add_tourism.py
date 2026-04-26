"""
Migration: expand MCC choices, add 'tourism' category type, add extra_costs_json field.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_systemconfiguration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='businessanalysisrequest',
            name='business_category_type',
            field=models.CharField(
                choices=[
                    ('hotel',        'Mehmonxona'),
                    ('tourism',      'Turizm'),
                    ('construction', 'Qurilish'),
                    ('textile',      'Tekstil sanoati'),
                    ('trade',        'Savdo & Chakana'),
                    ('services',     "Xizmat ko'rsatish"),
                ],
                default='hotel',
                max_length=20,
                verbose_name='Biznes kategoriyasi turi',
            ),
        ),
        migrations.AlterField(
            model_name='businessanalysisrequest',
            name='mcc_code',
            field=models.CharField(
                choices=[
                    ('7011', 'Mehmonxona / Hotel'),
                    ('7012', 'Apart-hotel / Vaqtinchalik yashash'),
                    ('4722', 'Sayohat agentligi / Tur operator'),
                    ('7991', 'Dam olish maskani / Attraktsion'),
                    ('5812', 'Restoran / Kafe'),
                    ('5251', "Qurilish mollari do'koni"),
                    ('5065', 'Elektr materiallari va jihozlar'),
                    ('5039', "Qurilish xom-ashyo (yog'och, qum, tsement)"),
                    ('7389', "Qurilish pudrat va ta'mirlash xizmati"),
                    ('5661', "Kiyim-kechak do'koni / Chakana"),
                    ('5131', "To'qimachilik va mato — ulgurji"),
                    ('5137', 'Forma va maxsus kiyimlar'),
                    ('5699', 'Kiyim-kechak (boshqa)'),
                    ('5411', "Oziq-ovqat do'koni / Supermarket"),
                    ('5912', 'Dorixona / Apteka'),
                    ('5200', "Uy jihozlari / Mebel do'koni"),
                    ('5310', "Chegirmali / Universal do'kon"),
                    ('5945', "O'yinchoq / Hobby do'koni"),
                    ('7299', "Maishiy xizmatlar (go'zallik, sartaroshxona)"),
                    ('8099', "Tibbiy va sog'liqni saqlash xizmatlari"),
                    ('8011', 'Shifokorlar / Klinikalar'),
                    ('7372', "IT va dasturiy ta'minot xizmatlari"),
                    ('8049', 'Stomatologiya va tibbiy mutaxassis'),
                    ('5999', 'Boshqa chakana savdo / Umumiy'),
                ],
                max_length=10,
                verbose_name='MCC Kategoriya',
            ),
        ),
        migrations.AddField(
            model_name='businessanalysisrequest',
            name='extra_costs_json',
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name='Qo\'shimcha xarajatlar (JSON)',
            ),
        ),
    ]
