from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import threading

_dossier_lock = threading.Lock()


def prochain_jour_ouvre(date_ref):
    jour = date_ref + timedelta(days=1)
    while jour.weekday() >= 5:
        jour += timedelta(days=1)
    return jour


def generer_numero_permis():
    with _dossier_lock:
        dernier = Candidat.objects.exclude(
            numero_permis__isnull=True
        ).exclude(numero_permis='').order_by('-numero_permis').first()
        if dernier and dernier.numero_permis.startswith('TI'):
            try:
                seq = int(dernier.numero_permis[2:]) + 1
            except ValueError:
                seq = 70000900 + Candidat.objects.count()
        else:
            seq = 70000900
        return f"TI{seq:08d}"


def prochain_numero_dossier():
    """Numéro séquentiel basé uniquement sur les dossiers normaux (pas les anciens)."""
    with _dossier_lock:
        # On prend le max numérique parmi tous les dossiers
        candidats = Candidat.objects.all()
        max_num = 1000
        for c in candidats:
            try:
                n = int(c.numero_dossier)
                if n > max_num:
                    max_num = n
            except (ValueError, TypeError):
                pass
        return max_num + 1


class AutoEcole(models.Model):
    nom = models.CharField(max_length=200, unique=True)
    responsable = models.CharField(max_length=200, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.CharField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auto-école"
        verbose_name_plural = "Auto-écoles"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Examinateur(models.Model):
    nom = models.CharField(max_length=200)
    prenom = models.CharField(max_length=200, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Examinateur"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()


class ProfilAgent(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('direction', 'Agent Direction'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='direction')
    telephone = models.CharField(max_length=20, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"


class CategoriePermis(models.Model):
    code = models.CharField(max_length=5, unique=True)
    libelle = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Catégorie de permis"
        verbose_name_plural = "Catégories de permis"
        ordering = ['ordre', 'code']

    def __str__(self):
        return self.code


class Candidat(models.Model):
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]
    CATEGORIE_CHOICES = [
        ('A1', 'A1'), ('A', 'A'), ('B', 'B'), ('C', 'C'),
        ('D', 'D'), ('E', 'E'), ('F', 'F'),
    ]

    numero_dossier = models.CharField(max_length=20, unique=True, db_index=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=150)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    telephone = models.CharField(max_length=20, blank=True)
    auto_ecole = models.ForeignKey(AutoEcole, on_delete=models.PROTECT, related_name='candidats')
    categorie = models.CharField(max_length=2, choices=CATEGORIE_CHOICES)
    date_inscription = models.DateField(auto_now_add=True)
    numero_permis = models.CharField(max_length=20, blank=True, null=True, unique=True)
    # Pour anciens dossiers migrés
    est_ancien_dossier = models.BooleanField(default=False)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='candidats_crees')

    class Meta:
        verbose_name = "Candidat"
        ordering = ['-date_inscription', 'nom']

    def __str__(self):
        return f"{self.numero_dossier} — {self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        if not self.numero_dossier:
            self.numero_dossier = str(prochain_numero_dossier())
        super().save(*args, **kwargs)

    @property
    def dernier_examen_code(self):
        return self.examens_code.order_by('-date_examen', '-id').first()

    @property
    def dernier_examen_conduite(self):
        return self.examens_conduite.order_by('-date_examen', '-id').first()

    @property
    def est_apte_complet(self):
        ec = self.dernier_examen_code
        ed = self.dernier_examen_conduite
        return bool(ec and ec.resultat == 'APTE' and ed and ed.resultat == 'APTE')

    @property
    def statut_global(self):
        ed = self.dernier_examen_conduite
        if ed and ed.resultat == 'APTE':
            return 'Permis délivré'
        ec = self.dernier_examen_code
        if not ec:
            return 'En attente code'
        if ec.resultat == 'APTE':
            return 'Apte code — en attente conduite'
        return 'En cours'


class ExamenCode(models.Model):
    RESULTAT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('APTE', 'Apte'),
        ('INAPTE', 'Inapte'),
        ('ABSENT', 'Absent'),
    ]
    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='examens_code')
    date_examen = models.DateField()
    note = models.PositiveSmallIntegerField(null=True, blank=True)
    resultat = models.CharField(max_length=15, choices=RESULTAT_CHOICES, default='EN_ATTENTE')
    date_saisie = models.DateTimeField(null=True, blank=True)
    saisi_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='examens_code_saisis')

    class Meta:
        verbose_name = "Examen code"
        ordering = ['-date_examen', '-id']

    def __str__(self):
        return f"Code {self.candidat.numero_dossier} — {self.date_examen}"

    def determiner_resultat(self):
        if self.note is not None:
            self.resultat = 'APTE' if self.note >= 18 else 'INAPTE'

    def date_min_reprogrammation(self):
        if self.resultat == 'INAPTE':
            date_min = self.date_examen + timedelta(days=7)
            if date_min.weekday() < 5:
                return date_min
            return prochain_jour_ouvre(date_min - timedelta(days=1))
        return None


class ExamenConduite(models.Model):
    RESULTAT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('APTE', 'Apte'),
        ('INAPTE', 'Inapte'),
        ('REPROGRAMME', 'Reprogrammé'),
        ('ABSENT', 'Absent'),
    ]
    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='examens_conduite')
    date_examen = models.DateField()
    examinateur = models.ForeignKey(Examinateur, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='examens')
    resultat = models.CharField(max_length=15, choices=RESULTAT_CHOICES, default='EN_ATTENTE')
    date_saisie = models.DateTimeField(null=True, blank=True)
    saisi_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='examens_conduite_saisis')

    class Meta:
        verbose_name = "Examen conduite"
        ordering = ['-date_examen', '-id']

    def __str__(self):
        return f"Conduite {self.candidat.numero_dossier} — {self.date_examen}"


class ParametreImpression(models.Model):
    """Position (en mm depuis le coin haut-gauche de la feuille A4) de chaque
    champ de données sur un document imprimé sur papier pré-imprimé."""
    TYPE_FICHE_CHOICES = [
        ('fiche_controle', 'Fiche contrôle candidat'),
        ('fiche_examen_code', "Fiche d'examen code"),
        ('fiche_examen_conduite', "Fiche d'examen conduite"),
        ('attestation', 'Attestation provisoire'),
    ]
    type_fiche = models.CharField(max_length=30, choices=TYPE_FICHE_CHOICES)
    champ = models.CharField(max_length=50)          # ex: 'nom', 'prenom', 'qr_code'
    label = models.CharField(max_length=100, blank=True)  # libellé humain affiché dans l'éditeur
    x_mm = models.FloatField(default=20)              # position horizontale en mm
    y_mm = models.FloatField(default=20)              # position verticale en mm
    taille_police = models.IntegerField(default=12)
    largeur_mm = models.FloatField(default=60, blank=True, null=True)  # utile pour le QR code
    visible = models.BooleanField(default=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Position de champ imprimé"
        verbose_name_plural = "Positions des champs imprimés"
        unique_together = [('type_fiche', 'champ')]
        ordering = ['type_fiche', 'y_mm', 'x_mm']

    def __str__(self):
        return f"{self.get_type_fiche_display()} — {self.label or self.champ}"


class JournalAudit(models.Model):
    ACTION_CHOICES = [
        ('CONNEXION', 'Connexion'),
        ('DECONNEXION', 'Déconnexion'),
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('SUPPRESSION', 'Suppression'),
        ('SAISIE_RESULTAT', 'Saisie résultat'),
    ]
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    modele = models.CharField(max_length=50, blank=True)
    objet_id = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ['-date_action']

    def __str__(self):
        return f"{self.date_action:%d/%m/%Y %H:%M} — {self.utilisateur} — {self.action}"


# ─── CHAMPS DISPONIBLES PAR TYPE DE FICHE (pour l'éditeur de positionnement) ──

CHAMPS_PAR_FICHE = {
    'fiche_controle': [
        ('numero_permis', 'N° du permis'),
        ('nom_complet', 'Nom et prénom (dénomination)'),
        ('nom', 'Nom'),
        ('prenom', 'Prénom'),
        ('date_lieu_naissance', 'Date et lieu de naissance'),
        ('auto_ecole', "Auto-école"),
    ],
    'fiche_examen_code': [
        ('date_jour', "Date du jour (Niamey le)"),
        ('date_examen', "Date d'examen"),
        ('numero_examen', "N° d'examen"),
        ('nom', 'Nom'),
        ('prenom', 'Prénom'),
        ('numero_dossier', 'N° Dossier'),
        ('auto_ecole', "Auto-école"),
    ],
    'fiche_examen_conduite': [
        ('date_jour', "Date du jour (Niamey le)"),
        ('date_examen', "Date d'examen"),
        ('numero_examen', "N° d'examen"),
        ('nom', 'Nom'),
        ('prenom', 'Prénom'),
        ('numero_dossier', 'N° Dossier'),
        ('auto_ecole', "Auto-école"),
    ],
    'attestation': [
        ('frais', 'Frais perçus'),
        ('nom', 'Nom'),
        ('prenom', 'Prénom'),
        ('date_lieu_naissance', 'Date et lieu de naissance'),
        ('numero_dossier_categorie', 'N° Dossier + Catégorie'),
        ('date_validite', 'Date début validité'),
        ('qr_code', 'QR Code de vérification'),
    ],
}
