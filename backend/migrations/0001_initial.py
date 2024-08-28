from django.db import migrations, models
from backend.models import Document

class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('original_file', models.FileField(upload_to='%Y/%m/%d/originals/')),
                ('translated_file', models.FileField(blank=True, null=True, upload_to='%Y/%m/%d/translations/')),
                ('translation_language', models.CharField(choices=Document.LANGUAGES_CHOICES, max_length=2)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
