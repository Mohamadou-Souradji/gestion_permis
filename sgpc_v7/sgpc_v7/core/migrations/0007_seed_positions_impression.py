from django.db import migrations

# Positions par défaut en mm depuis le coin haut-gauche d'une page A4 (210x297mm)
DEFAULTS = {
    'fiche_controle': [
        ('numero_permis', 'N° du permis', 90, 28, 11),
        ('nom_complet', 'Nom et prénom (dénomination)', 90, 45, 11),
        ('nom', 'Nom', 90, 52, 11),
        ('prenom', 'Prénom', 90, 59, 11),
        ('date_lieu_naissance', 'Date et lieu de naissance', 90, 66, 11),
        ('auto_ecole', "Auto-école", 90, 73, 10),
    ],
    'fiche_examen_code': [
        ('date_jour', "Date du jour (Niamey le)", 150, 15, 11),
        ('date_examen', "Date d'examen", 40, 28, 11),
        ('numero_examen', "N° d'examen", 40, 35, 11),
        ('nom', 'Nom', 40, 42, 11),
        ('prenom', 'Prénom', 40, 49, 11),
        ('numero_dossier', 'N° Dossier', 40, 56, 11),
        ('auto_ecole', "Auto-école", 40, 63, 10),
    ],
    'fiche_examen_conduite': [
        ('date_jour', "Date du jour (Niamey le)", 150, 15, 11),
        ('date_examen', "Date d'examen", 40, 30, 11),
        ('numero_examen', "N° d'examen", 40, 37, 11),
        ('nom', 'Nom', 40, 44, 11),
        ('prenom', 'Prénom', 40, 51, 11),
        ('numero_dossier', 'N° Dossier', 40, 58, 11),
        ('auto_ecole', "Auto-école", 40, 65, 10),
    ],
    'attestation': [
        ('frais', 'Frais perçus', 90, 60, 11),
        ('nom', 'Nom', 60, 90, 12),
        ('prenom', 'Prénom', 60, 100, 12),
        ('date_lieu_naissance', 'Date et lieu de naissance', 60, 110, 11),
        ('numero_dossier_categorie', 'N° Dossier + Catégorie', 60, 120, 11),
        ('date_validite', 'Date début validité', 75, 155, 12),
        ('qr_code', 'QR Code de vérification', 160, 240, 11),
    ],
}


def seed_positions(apps, schema_editor):
    ParametreImpression = apps.get_model('core', 'ParametreImpression')
    for type_fiche, champs in DEFAULTS.items():
        for champ, label, x, y, taille in champs:
            ParametreImpression.objects.get_or_create(
                type_fiche=type_fiche, champ=champ,
                defaults={'label': label, 'x_mm': x, 'y_mm': y, 'taille_police': taille}
            )


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_parametreimpression'),
    ]

    operations = [
        migrations.RunPython(seed_positions, reverse_seed),
    ]
