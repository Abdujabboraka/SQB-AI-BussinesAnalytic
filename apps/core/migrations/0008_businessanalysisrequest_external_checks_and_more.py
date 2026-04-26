# Hand-written migration: store external source-backed checks for result pages.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_unique_selling_point'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessanalysisrequest',
            name='external_checks',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name="Tashqi manbalar bo'yicha tekshiruvlar",
            ),
        ),
        migrations.AddField(
            model_name='businessanalysisrequest',
            name='external_checks_updated_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Tashqi tekshiruv yangilangan vaqti',
            ),
        ),
    ]

