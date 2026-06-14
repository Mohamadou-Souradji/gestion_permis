from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import threading
import random

# Verrou pour la génération atomique du numéro de dossier
_dossier_lock = threading.Lock()


def prochain_jour_ouvre(date_ref):
    """Retourne le prochain jour ouvré (lun-ven) à partir de date_ref."""
    jour = date_ref + timedelta(days=1)
    while jour.weekday() >= 5:
        jour += timedelta(days=1)
    return jour


def generer_numero_permis():
    """Génère un numéro de permis provisoire au format TIxxxxxxxx."""
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


def generer_numero_dossier():
    """Génère un numéro de dossier à 6 chiffres aléatoires unique."""
    with _dossier_lock:
        for _ in range(100):
            numero = str(random.randint(100000, 999999))
            if not Candidat.objects.filter(numero_dossier=numero).exists():
                return numero
        # Fallback : séquentiel si collisions répétées
        dernier = Candidat.objects.order_by('-id').first()
        return str((int(dernier.numero_dossier) + 1) if dernier else 100001)


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
    numero_cni = models.CharField(max_length=50, blank=True, verbose_name="N° CNI")
    adresse = models.CharField(max_length=300, blank=True)
    auto_ecole = models.ForeignKey(AutoEcole, on_delete=models.PROTECT, related_name='candidats')
    categorie = models.CharField(max_length=2, choices=CATEGORIE_CHOICES)
    date_inscription = models.DateField(auto_now_add=True)
    numero_permis = models.CharField(max_length=20, blank=True, null=True, unique=True,
                                       verbose_name="N° Permis (provisoire)")
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='candidats_crees')

    class Meta:
        verbose_name = "Candidat"
        ordering = ['-date_inscription', 'nom']

    def __str__(self):
        return f"{self.numero_dossier} — {self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        if not self.numero_dossier:
            self.numero_dossier = generer_numero_dossier()
        super().save(*args, **kwargs)

    @property
    def dernier_examen_code(self):
        return self.examens_code.order_by('-date_examen').first()

    @property
    def dernier_examen_conduite(self):
        return self.examens_conduite.order_by('-date_examen').first()

    @property
    def est_apte_complet(self):
        """True si le candidat est APTE au code ET à la conduite."""
        ec = self.dernier_examen_code
        ed = self.dernier_examen_conduite
        return bool(ec and ec.resultat == 'APTE' and ed and ed.resultat == 'APTE')

    @property
    def statut_global(self):
        ec = self.dernier_examen_conduite
        if ec and ec.resultat == 'APTE':
            return 'Permis délivré'
        ecode = self.dernier_examen_code
        if not ecode:
            return 'En attente code'
        if ecode.resultat == 'APTE':
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
    saisi_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Examen code"
        ordering = ['-date_examen']

    def __str__(self):
        return f"Code {self.candidat.numero_dossier} — {self.date_examen}"

    def determiner_resultat(self):
        if self.note is not None:
            if self.note >= 18:
                self.resultat = 'APTE'
            else:
                self.resultat = 'INAPTE'

    def prochaine_date_programmable(self):
        """INAPTE : j+7 calendaires minimum, puis prochain jour ouvré.
           ABSENT : J+1 ouvré."""
        if self.resultat == 'INAPTE':
            # Au plus tôt : date_examen + 7 jours calendaires
            date_min = self.date_examen + timedelta(days=7)
            # Si date_min est ouvré, on le garde; sinon prochain ouvré
            if date_min.weekday() < 5:
                return date_min
            return prochain_jour_ouvre(date_min - timedelta(days=1))
        elif self.resultat == 'ABSENT':
            return prochain_jour_ouvre(date.today())
        return None


class ExamenConduite(models.Model):
    RESULTAT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('APTE', 'Apte'),
        ('INAPTE', 'Inapte'),
        ('ABSENT', 'Absent'),
    ]
    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='examens_conduite')
    date_examen = models.DateField()
    note = models.PositiveSmallIntegerField(null=True, blank=True)
    resultat = models.CharField(max_length=15, choices=RESULTAT_CHOICES, default='EN_ATTENTE')
    date_saisie = models.DateTimeField(null=True, blank=True)
    saisi_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Examen conduite"
        ordering = ['-date_examen']

    def __str__(self):
        return f"Conduite {self.candidat.numero_dossier} — {self.date_examen}"

    def determiner_resultat(self):
        if self.note is not None:
            if self.note >= 18:
                self.resultat = 'APTE'
            else:
                self.resultat = 'INAPTE'

    def prochaine_date_programmable(self):
        """INAPTE : j+7 calendaires minimum, puis prochain jour ouvré.
           ABSENT : J+1 ouvré. (conduite seulement — pas de retour au code)"""
        if self.resultat == 'INAPTE':
            date_min = self.date_examen + timedelta(days=7)
            if date_min.weekday() < 5:
                return date_min
            return prochain_jour_ouvre(date_min - timedelta(days=1))
        elif self.resultat == 'ABSENT':
            return prochain_jour_ouvre(date.today())
        return None


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
