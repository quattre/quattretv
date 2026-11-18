from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0004_avisos'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='aspecto',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
