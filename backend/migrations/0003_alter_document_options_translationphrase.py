# Generated by Django 5.1 on 2024-09-03 20:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0002_appconfig_alter_document_original_file_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='document',
            options={'verbose_name': 'Документ', 'verbose_name_plural': 'Документы'},
        ),
        migrations.CreateModel(
            name='TranslationPhrase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_language', models.CharField(help_text="Исходный язык фразы, например, 'en'.", max_length=10)),
                ('target_language', models.CharField(help_text="Целевой язык перевода, например, 'ru'.", max_length=10)),
                ('source_phrase', models.CharField(help_text='Фраза на исходном языке.', max_length=255)),
                ('translated_phrase', models.CharField(help_text='Фраза на целевом языке.', max_length=255)),
            ],
            options={
                'unique_together': {('source_language', 'target_language', 'source_phrase')},
            },
        ),
    ]