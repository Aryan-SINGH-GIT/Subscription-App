# Generated migration for adding overage and rate limiting to Plan model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0002_alter_feature_code_alter_plan_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan',
            name='billing_period',
            field=models.CharField(
                choices=[
                    ('monthly', 'Monthly'),
                    ('yearly', 'Yearly'),
                    ('hourly', 'Hourly'),
                    ('minute', 'Per Minute')
                ],
                default='monthly',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='plan',
            name='overage_price',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Price per unit when usage exceeds limit (0 = no overage billing)',
                max_digits=10
            ),
        ),
        migrations.AddField(
            model_name='plan',
            name='rate_limit',
            field=models.IntegerField(
                default=0,
                help_text='Max calls per rate_limit_window seconds (0 = no rate limiting)'
            ),
        ),
        migrations.AddField(
            model_name='plan',
            name='rate_limit_window',
            field=models.IntegerField(
                default=60,
                help_text='Time window in seconds for rate limiting (default: 60 = 1 minute)'
            ),
        ),
    ]

