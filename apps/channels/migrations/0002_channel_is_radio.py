from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0001_initial_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='is_radio',
            field=models.BooleanField(default=False, help_text='Radio station instead of TV channel'),
        ),
    ]
