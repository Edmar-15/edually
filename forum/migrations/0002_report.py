from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('forum', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.CharField(choices=[('post', 'Post'), ('reply', 'Reply')], max_length=10)),
                ('reason', models.CharField(max_length=50)),
                ('description', models.TextField(blank=True)),
                ('is_resolved', models.BooleanField(default=False)),
                ('action_taken', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='forum.post')),
                ('reply', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='forum.reply')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forum_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='report',
            constraint=models.CheckConstraint(
                condition=models.Q(('content_type', 'post'), ('post__isnull', False), ('reply__isnull', True)) | models.Q(('content_type', 'reply'), ('post__isnull', True), ('reply__isnull', False)),
                name='report_matches_content_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='report',
            constraint=models.UniqueConstraint(fields=('reporter', 'content_type', 'post', 'reply'), name='one_report_per_user_content'),
        ),
    ]