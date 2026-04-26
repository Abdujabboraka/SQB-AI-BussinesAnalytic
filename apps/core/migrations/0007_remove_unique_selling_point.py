# Hand-written migration: remove redundant unique-selling-point field.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_add_services_category_choice'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='businessanalysisrequest',
            name='unique_selling_point',
        ),
    ]
