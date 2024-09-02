# Generated by Django 5.1 on 2024-08-30 18:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('value', models.TextField()),
            ],
            options={
                'verbose_name': 'Настройка',
                'verbose_name_plural': 'Настройки',
            },
        ),
        migrations.AlterField(
            model_name='document',
            name='original_file',
            field=models.FileField(upload_to='tmp/originals/'),
        ),
        migrations.AlterField(
            model_name='document',
            name='translated_file',
            field=models.FileField(blank=True, null=True, upload_to='tmp/translations/'),
        ),
        migrations.AlterField(
            model_name='document',
            name='translation_language',
            field=models.CharField(choices=[('RU', 'Русский'), ('EN', 'Английский'), ('ES', 'Испанский'), ('IT', 'Итальянский'), ('DE', 'Немецкий'), ('FR', 'Французский'), ('AR', 'Арабский'), ('AZ', 'Азербайджанский'), ('BE', 'Белорусский'), ('BN', 'Бенгальский'), ('BS', 'Боснийский'), ('PT-BR', 'Бразильский Португальский'), ('BG', 'Болгарский'), ('YUE', 'Кантонский диалект (юэ)'), ('CA', 'Каталонский'), ('ZH', 'Китайский'), ('HR', 'Хорватский'), ('CS', 'Чешский'), ('DA', 'Датский'), ('NL', 'Голландский'), ('ET', 'Эстонский'), ('FI', 'Финский'), ('EL', 'Греческий'), ('GU', 'Гуджарати'), ('HI', 'Хинди'), ('HU', 'Венгерский'), ('ID', 'Индонезийский'), ('GA', 'Ирландский'), ('JA', 'Японский'), ('KZ', 'Казахский'), ('KO', 'Корейский'), ('KY', 'Кыргызский'), ('LV', 'Латышский'), ('LT', 'Литовский'), ('MK', 'Македонский'), ('MS', 'Малайский'), ('MT', 'Мальтийский'), ('CMN', 'Мандарин'), ('MR', 'Маратхи'), ('MO', 'Молдавский'), ('MN', 'Монгольский'), ('NE', 'Непальский'), ('NO', 'Норвежский'), ('PL', 'Польский'), ('PT', 'Португальский'), ('PA', 'Панджаби'), ('RO', 'Румынский'), ('SR', 'Сербский'), ('SK', 'Словацкий'), ('SL', 'Словенский'), ('SW', 'Суахили'), ('SV', 'Шведский'), ('TG', 'Таджикский'), ('TA', 'Тамильский'), ('TT', 'Татарский'), ('TE', 'Телугу'), ('TH', 'Тайский'), ('TR', 'Турецкий'), ('TK', 'Туркменский'), ('UK', 'Украинcкий'), ('UR', 'Урду'), ('UZ', 'Узбекский'), ('VI', 'Вьетнамский')], max_length=5),
        ),
    ]