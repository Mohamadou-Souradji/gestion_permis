from django.db import migrations


def seed_categories(apps, schema_editor):
    CategoriePermis = apps.get_model('core', 'CategoriePermis')
    codes = ['A1', 'A', 'B', 'C', 'D', 'E', 'F']
    for i, code in enumerate(codes):
        CategoriePermis.objects.get_or_create(code=code, defaults={'ordre': i})


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_categoriepermis'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_seed),
    ]
