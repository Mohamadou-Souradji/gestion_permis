from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, timedelta
from .models import (
    AutoEcole, Examinateur, ProfilAgent, Candidat, ExamenCode, ExamenConduite,
    JournalAudit, CategoriePermis, ParametreImpression,
    prochain_jour_ouvre, generer_numero_permis, prochain_numero_dossier
)
from .decorators import role_required


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


# ─── AUTH ──────────────────────────────────────────────────────────────────────

def connexion(request):
    if request.user.is_authenticated:
        return redirect('tableau_de_bord')
    if request.method == 'POST':
        user = authenticate(request,
                            username=request.POST.get('username', '').strip(),
                            password=request.POST.get('password', ''))
        if user and user.is_active:
            profil = getattr(user, 'profil', None)
            if profil and profil.actif:
                login(request, user)
                JournalAudit.objects.create(
                    utilisateur=user, action='CONNEXION',
                    description=f'Connexion depuis {get_client_ip(request)}',
                    adresse_ip=get_client_ip(request))
                return redirect('tableau_de_bord')
            messages.error(request, "Compte désactivé. Contactez l'administrateur.")
        else:
            messages.error(request, "Identifiant ou mot de passe incorrect.")
    return render(request, 'core/connexion.html')


@login_required
def deconnexion(request):
    JournalAudit.objects.create(
        utilisateur=request.user, action='DECONNEXION',
        adresse_ip=get_client_ip(request))
    logout(request)
    return redirect('connexion')


# ─── TABLEAU DE BORD ───────────────────────────────────────────────────────────

@login_required
def tableau_de_bord(request):
    aujourd_hui = date.today()
    ctx = {
        'total_candidats': Candidat.objects.count(),
        'examens_aujourd_hui': (
            ExamenCode.objects.filter(date_examen=aujourd_hui, resultat='EN_ATTENTE').count() +
            ExamenConduite.objects.filter(date_examen=aujourd_hui, resultat='EN_ATTENTE').count()
        ),
        'aptes_code': ExamenCode.objects.filter(resultat='APTE').values('candidat').distinct().count(),
        'permis_delivres': ExamenConduite.objects.filter(resultat='APTE').count(),
        'examens_code_aujourd_hui': ExamenCode.objects.filter(
            date_examen=aujourd_hui).select_related('candidat', 'candidat__auto_ecole'),
        'examens_conduite_aujourd_hui': ExamenConduite.objects.filter(
            date_examen=aujourd_hui).select_related('candidat', 'candidat__auto_ecole'),
    }
    return render(request, 'core/tableau_de_bord.html', ctx)


# ─── CANDIDATS ─────────────────────────────────────────────────────────────────

@login_required
def liste_candidats(request):
    q = request.GET.get('q', '').strip()
    categorie = request.GET.get('categorie', '').strip()
    auto_ecole = request.GET.get('auto_ecole', '').strip()
    a_filtre = any([q, categorie, auto_ecole])
    candidats = []
    if a_filtre:
        qs = Candidat.objects.select_related('auto_ecole').all()
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) |
                           Q(numero_dossier__icontains=q))
        if categorie:
            qs = qs.filter(categorie=categorie)
        if auto_ecole:
            qs = qs.filter(auto_ecole_id=auto_ecole)
        candidats = qs.order_by('-id')
    return render(request, 'core/candidats/liste.html', {
        'candidats': candidats,
        'a_filtre': a_filtre,
        'q': q, 'categorie': categorie, 'auto_ecole': auto_ecole,
        'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
        'auto_ecoles': AutoEcole.objects.order_by('nom'),
    })


@login_required
def creer_candidat(request):
    prochain_num = prochain_numero_dossier()
    if request.method == 'POST':
        num = request.POST.get('numero_dossier', '').strip()
        # Vérifier si numéro déjà pris
        if num and Candidat.objects.filter(numero_dossier=num).exists():
            messages.error(request, f"Le numéro de dossier {num} existe déjà. Choisissez un autre numéro.")
            return render(request, 'core/candidats/form.html', {
                'auto_ecoles': AutoEcole.objects.filter(actif=True).order_by('nom'),
                'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
                'sexes': Candidat.SEXE_CHOICES,
                'prochain_num': prochain_num,
                'post': request.POST,
            })
        try:
            auto_ecole = AutoEcole.objects.get(id=request.POST['auto_ecole'])
            candidat = Candidat(
                nom=request.POST['nom'].upper(),
                prenom=request.POST['prenom'],
                date_naissance=request.POST['date_naissance'],
                lieu_naissance=request.POST['lieu_naissance'],
                sexe=request.POST['sexe'],
                telephone=request.POST.get('telephone', ''),
                auto_ecole=auto_ecole,
                categorie=request.POST['categorie'],
                cree_par=request.user,
            )
            if num:
                candidat.numero_dossier = num
            candidat.save()
            date_code = prochain_jour_ouvre(date.today())
            ExamenCode.objects.create(candidat=candidat, date_examen=date_code)
            JournalAudit.objects.create(
                utilisateur=request.user, action='CREATION',
                modele='Candidat', objet_id=candidat.numero_dossier,
                description=f'Nouveau candidat : {candidat.nom} {candidat.prenom}',
                adresse_ip=get_client_ip(request))
            messages.success(request,
                f"Dossier {candidat.numero_dossier} créé. Code programmé le {date_code.strftime('%d/%m/%Y')}.")
            return redirect('detail_candidat', pk=candidat.pk)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return render(request, 'core/candidats/form.html', {
        'auto_ecoles': AutoEcole.objects.filter(actif=True).order_by('nom'),
        'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
        'sexes': Candidat.SEXE_CHOICES,
        'prochain_num': prochain_num,
    })


@login_required
def detail_candidat(request, pk):
    candidat = get_object_or_404(Candidat, pk=pk)
    examinateurs = Examinateur.objects.filter(actif=True)
    return render(request, "core/candidats/detail.html", {
        'candidat': candidat,
        'examinateurs': examinateurs,
    })


@login_required
def modifier_date_examen_code(request, pk):
    examen = get_object_or_404(ExamenCode, pk=pk)
    if request.method == 'POST':
        nouvelle_date = request.POST.get('nouvelle_date')
        if nouvelle_date:
            examen.date_examen = nouvelle_date
            examen.save()
            from datetime import date as date_type
            d = date_type.fromisoformat(nouvelle_date)
            messages.success(request, f"Date code modifiée : {d.strftime('%d/%m/%Y')}.")
    return redirect('detail_candidat', pk=examen.candidat.pk)


@login_required
def modifier_date_examen_conduite(request, pk):
    examen = get_object_or_404(ExamenConduite, pk=pk)
    if request.method == 'POST':
        nouvelle_date = request.POST.get('nouvelle_date')
        examinateur_id = request.POST.get('examinateur')
        if nouvelle_date:
            examen.date_examen = nouvelle_date
        if examinateur_id:
            examen.examinateur_id = examinateur_id
        examen.save()
        from datetime import date as date_type
        d = date_type.fromisoformat(str(examen.date_examen))
        messages.success(request, f"Date conduite modifiée : {d.strftime('%d/%m/%Y')}.")
    return redirect('detail_candidat', pk=examen.candidat.pk)


@login_required
def programmer_conduite(request, pk):
    """Programme un examen conduite — bloque si déjà en attente, vérifie date > code."""
    candidat = get_object_or_404(Candidat, pk=pk)
    if request.method == 'POST':
        nouvelle_date_str = request.POST.get('date_conduite', '').strip()
        examinateur_id = request.POST.get('examinateur', '').strip()

        if not nouvelle_date_str:
            messages.error(request, "Veuillez choisir une date.")
            return redirect('detail_candidat', pk=pk)

        # Bloquer si un examen conduite est déjà EN_ATTENTE
        deja_programme = ExamenConduite.objects.filter(
            candidat=candidat, resultat='EN_ATTENTE').exists()
        if deja_programme:
            messages.error(request,
                "Ce candidat a déjà une conduite programmée en attente. "
                "Saisissez le résultat avant de reprogrammer.")
            return redirect('detail_candidat', pk=pk)

        # La date conduite doit être >= date du dernier examen code
        from datetime import date as date_type
        nouvelle_date = date_type.fromisoformat(nouvelle_date_str)
        dernier_code = candidat.dernier_examen_code
        if dernier_code and nouvelle_date <= dernier_code.date_examen:
            messages.error(request,
                f"La date de conduite ({nouvelle_date.strftime('%d/%m/%Y')}) "
                f"doit être postérieure à la date du code ({dernier_code.date_examen.strftime('%d/%m/%Y')}).")
            return redirect('detail_candidat', pk=pk)

        ec = ExamenConduite(candidat=candidat, date_examen=nouvelle_date_str)
        if examinateur_id:
            ec.examinateur_id = examinateur_id
        ec.save()
        messages.success(request, f"Conduite programmée le {nouvelle_date.strftime('%d/%m/%Y')}.")
    return redirect('detail_candidat', pk=pk)


# ─── ANCIEN DOSSIER ────────────────────────────────────────────────────────────

@login_required
def saisir_ancien_dossier(request):
    """Saisie d'un dossier existant (migré depuis registre papier)."""
    ctx = {
        'auto_ecoles': AutoEcole.objects.filter(actif=True).order_by('nom'),
        'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
        'sexes': Candidat.SEXE_CHOICES,
    }
    if request.method == 'POST':
        num = request.POST.get('numero_dossier', '').strip()
        if not num:
            messages.error(request, "Le numéro de dossier est obligatoire.")
            return render(request, 'core/candidats/ancien_dossier.html', ctx)

        # Vérifier si le numéro existe déjà
        if Candidat.objects.filter(numero_dossier=num).exists():
            messages.error(request,
                f"Le numéro de dossier {num} existe déjà dans le système. "
                f"Vérifiez le numéro ou consultez la fiche existante.")
            return render(request, 'core/candidats/ancien_dossier.html', ctx)

        try:
            auto_ecole = AutoEcole.objects.get(id=request.POST['auto_ecole'])
            code_valide = request.POST.get('code_valide') == '1'
            conduite_valide = request.POST.get('conduite_valide') == '1'

            candidat = Candidat.objects.create(
                numero_dossier=num,
                nom=request.POST['nom'].upper(),
                prenom=request.POST['prenom'],
                date_naissance=request.POST['date_naissance'],
                lieu_naissance=request.POST['lieu_naissance'],
                sexe=request.POST['sexe'],
                telephone=request.POST.get('telephone', ''),
                auto_ecole=auto_ecole,
                categorie=request.POST['categorie'],
                est_ancien_dossier=True,
                cree_par=request.user,
            )

            if code_valide:
                ExamenCode.objects.create(
                    candidat=candidat,
                    date_examen=request.POST.get('date_code') or date.today(),
                    resultat='APTE',
                    date_saisie=timezone.now(),
                    saisi_par=request.user,
                )
            else:
                date_prog = request.POST.get('date_code_prog') or ''
                if date_prog:
                    ExamenCode.objects.create(candidat=candidat, date_examen=date_prog)

            if conduite_valide and code_valide:
                ExamenConduite.objects.create(
                    candidat=candidat,
                    date_examen=request.POST.get('date_conduite') or date.today(),
                    resultat='APTE',
                    date_saisie=timezone.now(),
                    saisi_par=request.user,
                )
            elif code_valide and not conduite_valide:
                date_cond = request.POST.get('date_conduite_prog') or ''
                if date_cond:
                    ExamenConduite.objects.create(candidat=candidat, date_examen=date_cond)

            JournalAudit.objects.create(
                utilisateur=request.user, action='CREATION',
                modele='Candidat', objet_id=candidat.numero_dossier,
                description=f'Ancien dossier migré : {candidat.nom} {candidat.prenom}',
                adresse_ip=get_client_ip(request))
            messages.success(request, f"Ancien dossier {candidat.numero_dossier} enregistré.")
            return redirect('detail_candidat', pk=candidat.pk)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return render(request, 'core/candidats/ancien_dossier.html', ctx)


# ─── EXAMENS ───────────────────────────────────────────────────────────────────

@login_required
def examens_code_jour(request):
    jour_str = request.GET.get('date', date.today().isoformat())
    try:
        jour_dt = date.fromisoformat(jour_str)
    except ValueError:
        jour_dt = date.today()
    codes = ExamenCode.objects.filter(
        date_examen=jour_dt).select_related('candidat', 'candidat__auto_ecole')
    return render(request, 'core/examens/jour.html', {
        'type_examen': 'code', 'examens': codes,
        'jour': jour_dt, 'aujourd_hui': date.today(),
    })


@login_required
def examens_conduite_jour(request):
    jour_str = request.GET.get('date', date.today().isoformat())
    try:
        jour_dt = date.fromisoformat(jour_str)
    except ValueError:
        jour_dt = date.today()
    conduites = ExamenConduite.objects.filter(
        date_examen=jour_dt).select_related('candidat', 'candidat__auto_ecole', 'examinateur')
    return render(request, 'core/examens/jour.html', {
        'type_examen': 'conduite', 'examens': conduites,
        'jour': jour_dt, 'aujourd_hui': date.today(),
    })


@login_required
def saisir_resultat_code(request, pk):
    examen = get_object_or_404(ExamenCode, pk=pk)
    if request.method == 'POST':
        absent = request.POST.get('absent') == '1'
        if absent:
            examen.resultat = 'ABSENT'
            examen.note = None
        else:
            examen.note = int(request.POST.get('note', 0))
            examen.determiner_resultat()
        # Modifier la date si l'agent l'a changée
        nouvelle_date = request.POST.get('date_examen', '').strip()
        if nouvelle_date:
            examen.date_examen = nouvelle_date
        examen.date_saisie = timezone.now()
        examen.saisi_par = request.user
        examen.save()

        if examen.resultat == 'APTE':
            messages.success(request,
                "Apte au code. Programmez la conduite depuis la fiche candidat.")
        else:
            messages.info(request, f"Résultat : {examen.get_resultat_display()}")
        JournalAudit.objects.create(
            utilisateur=request.user, action='SAISIE_RESULTAT',
            modele='ExamenCode', objet_id=str(examen.pk),
            description=f'Code {examen.candidat.numero_dossier} : {examen.resultat}',
            adresse_ip=get_client_ip(request))
        return redirect('examens_code_jour')
    return render(request, 'core/examens/saisie_code.html', {'examen': examen})


@login_required
def saisir_resultat_conduite(request, pk):
    examen = get_object_or_404(ExamenConduite, pk=pk)
    examinateurs = Examinateur.objects.filter(actif=True)
    if request.method == 'POST':
        resultat = request.POST.get('resultat', 'EN_ATTENTE')
        examen.resultat = resultat
        examinateur_id = request.POST.get('examinateur')
        if examinateur_id:
            examen.examinateur_id = examinateur_id
        # Modifier date si changée
        nouvelle_date = request.POST.get('date_examen', '').strip()
        if nouvelle_date:
            examen.date_examen = nouvelle_date
        examen.date_saisie = timezone.now()
        examen.saisi_par = request.user
        examen.save()

        # Si reprogrammé/inapte/absent → créer nouvel examen conduite à la date choisie
        if resultat in ('INAPTE', 'REPROGRAMME', 'ABSENT'):
            date_reprog = request.POST.get('date_reprog', '').strip()
            examinateur_reprog = request.POST.get('examinateur_reprog', '')
            if date_reprog:
                ec = ExamenConduite(candidat=examen.candidat, date_examen=date_reprog)
                if examinateur_reprog:
                    ec.examinateur_id = examinateur_reprog
                ec.save()
                messages.info(request,
                    f"{examen.get_resultat_display()}. Conduite reprogrammée le {ec.date_examen.strftime('%d/%m/%Y')}.")
            else:
                messages.info(request,
                    f"Résultat : {examen.get_resultat_display()}. Pensez à reprogrammer la conduite depuis la fiche.")
        elif resultat == 'APTE':
            messages.success(request, "Candidat apte. Attestation disponible.")
        JournalAudit.objects.create(
            utilisateur=request.user, action='SAISIE_RESULTAT',
            modele='ExamenConduite', objet_id=str(examen.pk),
            description=f'Conduite {examen.candidat.numero_dossier} : {examen.resultat}',
            adresse_ip=get_client_ip(request))
        return redirect('examens_conduite_jour')
    return render(request, 'core/examens/saisie_conduite.html', {
        'examen': examen, 'examinateurs': examinateurs,
    })


@login_required
def imprimer_liste_examens(request, type_examen):
    jour_str = request.GET.get('date', date.today().isoformat())
    try:
        jour_dt = date.fromisoformat(jour_str)
    except ValueError:
        jour_dt = date.today()
    ordre = {'APTE': 0, 'INAPTE': 1, 'ABSENT': 2, 'REPROGRAMME': 3, 'EN_ATTENTE': 4}
    if type_examen == 'code':
        examens = list(ExamenCode.objects.filter(
            date_examen=jour_dt).select_related('candidat', 'candidat__auto_ecole'))
    else:
        examens = list(ExamenConduite.objects.filter(
            date_examen=jour_dt).select_related('candidat', 'candidat__auto_ecole', 'examinateur'))
    examens.sort(key=lambda e: ordre.get(e.resultat, 9))
    return render(request, 'core/examens/imprimer_liste.html', {
        'examens': examens, 'type_examen': type_examen, 'jour': jour_dt,
    })


# ─── ABSENTS ───────────────────────────────────────────────────────────────────

@login_required
def liste_absents(request):
    nom = request.GET.get('nom', '').strip()
    auto_ecole = request.GET.get('auto_ecole', '').strip()
    categorie = request.GET.get('categorie', '').strip()
    type_examen = request.GET.get('type_examen', '').strip()
    a_filtre = any([nom, auto_ecole, categorie, type_examen])

    absents_code = ExamenCode.objects.none()
    absents_conduite = ExamenConduite.objects.none()

    if a_filtre:
        absents_code = ExamenCode.objects.filter(
            resultat__in=['ABSENT', 'INAPTE']
        ).select_related('candidat', 'candidat__auto_ecole').order_by('-date_examen')
        absents_conduite = ExamenConduite.objects.filter(
            resultat__in=['ABSENT', 'INAPTE', 'REPROGRAMME']
        ).select_related('candidat', 'candidat__auto_ecole').order_by('-date_examen')

        if nom:
            absents_code = absents_code.filter(
                Q(candidat__nom__icontains=nom) | Q(candidat__prenom__icontains=nom))
            absents_conduite = absents_conduite.filter(
                Q(candidat__nom__icontains=nom) | Q(candidat__prenom__icontains=nom))
        if auto_ecole:
            absents_code = absents_code.filter(candidat__auto_ecole_id=auto_ecole)
            absents_conduite = absents_conduite.filter(candidat__auto_ecole_id=auto_ecole)
        if categorie:
            absents_code = absents_code.filter(candidat__categorie=categorie)
            absents_conduite = absents_conduite.filter(candidat__categorie=categorie)
        if type_examen == 'code':
            absents_conduite = absents_conduite.none()
        elif type_examen == 'conduite':
            absents_code = absents_code.none()

    return render(request, 'core/absents/liste.html', {
        'absents_code': absents_code, 'absents_conduite': absents_conduite,
        'a_filtre': a_filtre,
        'nom': nom, 'auto_ecole': auto_ecole, 'categorie': categorie,
        'type_examen': type_examen,
        'auto_ecoles': AutoEcole.objects.order_by('nom'),
        'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
        'examinateurs': Examinateur.objects.filter(actif=True),
    })


@login_required
def programmer_absent(request, pk, type_examen):
    if request.method == 'POST':
        nouvelle_date = request.POST.get('nouvelle_date', '')
        try:
            date.fromisoformat(nouvelle_date)
        except ValueError:
            messages.error(request, "Date invalide.")
            return redirect('liste_absents')
        if type_examen == 'code':
            examen = get_object_or_404(ExamenCode, pk=pk)
            ExamenCode.objects.create(candidat=examen.candidat, date_examen=nouvelle_date)
            messages.success(request, f"{examen.candidat.nom} reprogrammé au code le {nouvelle_date}.")
        elif type_examen == 'conduite':
            examen = get_object_or_404(ExamenConduite, pk=pk)
            examinateur_id = request.POST.get('examinateur', '')
            ec = ExamenConduite(candidat=examen.candidat, date_examen=nouvelle_date)
            if examinateur_id:
                ec.examinateur_id = examinateur_id
            ec.save()
            messages.success(request, f"{examen.candidat.nom} reprogrammé à la conduite le {nouvelle_date}.")
        JournalAudit.objects.create(
            utilisateur=request.user, action='MODIFICATION',
            description=f'Absent reprogrammé {type_examen} le {nouvelle_date}',
            adresse_ip=get_client_ip(request))
    return redirect('liste_absents')


# ─── ATTESTATIONS ──────────────────────────────────────────────────────────────

@login_required
def liste_attestations(request):
    nom = request.GET.get('nom', '').strip()
    numero_dossier = request.GET.get('numero_dossier', '').strip()
    auto_ecole = request.GET.get('auto_ecole', '').strip()
    categorie = request.GET.get('categorie', '').strip()
    a_filtre = any([nom, numero_dossier, auto_ecole, categorie])
    candidats = []
    if a_filtre:
        qs = Candidat.objects.select_related('auto_ecole').prefetch_related(
            'examens_code', 'examens_conduite')
        if nom:
            qs = qs.filter(Q(nom__icontains=nom) | Q(prenom__icontains=nom))
        if numero_dossier:
            qs = qs.filter(numero_dossier__icontains=numero_dossier)
        if auto_ecole:
            qs = qs.filter(auto_ecole_id=auto_ecole)
        if categorie:
            qs = qs.filter(categorie=categorie)
        candidats = [c for c in qs if c.est_apte_complet]
    return render(request, 'core/attestations/liste.html', {
        'candidats': candidats, 'a_filtre': a_filtre,
        'nom': nom, 'numero_dossier': numero_dossier,
        'auto_ecole': auto_ecole, 'categorie': categorie,
        'auto_ecoles': AutoEcole.objects.order_by('nom'),
        'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
    })


@login_required
def imprimer_attestation(request, pk):
    candidat = get_object_or_404(Candidat, pk=pk)
    if not candidat.est_apte_complet:
        messages.error(request, "Ce candidat n'a pas validé les deux examens.")
        return redirect('liste_attestations')
    if not candidat.numero_permis:
        candidat.numero_permis = generer_numero_permis()
        candidat.save()
    examen_conduite = candidat.dernier_examen_conduite
    date_delivrance = examen_conduite.date_examen if examen_conduite else date.today()

    qr_data_uri = generer_qr_attestation(request, candidat.pk)

    positions = ParametreImpression.objects.filter(type_fiche='attestation', visible=True)
    valeurs = {
        'frais': '2 000 CFA',
        'nom': candidat.nom.upper(),
        'prenom': candidat.prenom,
        'date_lieu_naissance': f"{candidat.date_naissance.strftime('%d/%m/%Y')}  {candidat.lieu_naissance.upper()}",
        'numero_dossier_categorie': f"{candidat.numero_dossier}   Catégorie {candidat.categorie}",
        'date_validite': date_delivrance.strftime('%d/%m/%Y'),
    }

    return render(request, 'core/attestations/imprimer.html', {
        'candidat': candidat,
        'date_delivrance': date_delivrance,
        'aujourd_hui': date.today(),
        'qr_data_uri': qr_data_uri,
        'positions': positions,
        'valeurs': valeurs,
    })


def generer_qr_attestation(request, candidat_pk):
    """Génère un QR code (data URI base64) pointant vers la vérification publique."""
    import qrcode
    import io
    import base64

    url = request.build_absolute_uri(f"/verification/{candidat_pk}/")
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f"data:image/png;base64,{encoded}"


def verification_attestation(request, pk):
    """Page publique consultée en scannant le QR code de l'attestation."""
    candidat = get_object_or_404(Candidat, pk=pk)
    est_valide = candidat.est_apte_complet
    return render(request, 'core/attestations/verification.html', {
        'candidat': candidat,
        'est_valide': est_valide,
    })


# ─── RAPPORTS ──────────────────────────────────────────────────────────────────

@login_required
def rapports(request):
    stats = {
        'par_categorie': Candidat.objects.values('categorie').annotate(total=Count('id')),
        'par_auto_ecole': Candidat.objects.values(
            'auto_ecole__nom').annotate(total=Count('id')).order_by('-total')[:10],
        'taux_reussite_code': ExamenCode.objects.exclude(resultat='EN_ATTENTE').aggregate(
            total=Count('id'), aptes=Count('id', filter=Q(resultat='APTE'))),
        'taux_reussite_conduite': ExamenConduite.objects.exclude(resultat='EN_ATTENTE').aggregate(
            total=Count('id'), aptes=Count('id', filter=Q(resultat='APTE'))),
    }
    return render(request, 'core/rapports.html', {'stats': stats})


# ─── ADMIN : AGENTS ────────────────────────────────────────────────────────────

@login_required
@role_required('admin')
def liste_agents(request):
    agents = ProfilAgent.objects.select_related('user').all()
    return render(request, 'core/admin/agents/liste.html', {'agents': agents})


@login_required
@role_required('admin')
def creer_agent(request):
    if request.method == 'POST':
        try:
            user = User.objects.create_user(
                username=request.POST['username'],
                password=request.POST['password'],
                first_name=request.POST['prenom'],
                last_name=request.POST['nom'],
                email=request.POST.get('email', ''),
            )
            ProfilAgent.objects.create(
                user=user, role=request.POST['role'],
                telephone=request.POST.get('telephone', ''))
            messages.success(request, f"Compte créé pour {user.get_full_name()}.")
            return redirect('liste_agents')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return render(request, 'core/admin/agents/form.html')


@login_required
@role_required('admin')
def toggle_agent(request, pk):
    profil = get_object_or_404(ProfilAgent, pk=pk)
    profil.actif = not profil.actif
    profil.save()
    messages.success(request, f"Compte {'activé' if profil.actif else 'désactivé'}.")
    return redirect('liste_agents')


# ─── ADMIN : AUTO-ÉCOLES ───────────────────────────────────────────────────────

@login_required
@role_required('admin')
def liste_auto_ecoles(request):
    q = request.GET.get('q', '')
    qs = AutoEcole.objects.annotate(nb_candidats=Count('candidats'))
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(responsable__icontains=q))
    return render(request, 'core/admin/auto_ecoles/liste.html', {'auto_ecoles': qs, 'q': q})


@login_required
@role_required('admin')
def creer_auto_ecole(request):
    if request.method == 'POST':
        try:
            ae = AutoEcole.objects.create(
                nom=request.POST['nom'],
                responsable=request.POST.get('responsable', ''),
                telephone=request.POST.get('telephone', ''),
                adresse=request.POST.get('adresse', ''),
                email=request.POST.get('email', ''),
            )
            messages.success(request, f"Auto-école « {ae.nom} » créée.")
            return redirect('liste_auto_ecoles')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return render(request, 'core/admin/auto_ecoles/form.html')


@login_required
@role_required('admin')
def modifier_auto_ecole(request, pk):
    ae = get_object_or_404(AutoEcole, pk=pk)
    if request.method == 'POST':
        ae.nom = request.POST['nom']
        ae.responsable = request.POST.get('responsable', '')
        ae.telephone = request.POST.get('telephone', '')
        ae.adresse = request.POST.get('adresse', '')
        ae.email = request.POST.get('email', '')
        ae.save()
        messages.success(request, "Auto-école mise à jour.")
        return redirect('liste_auto_ecoles')
    return render(request, 'core/admin/auto_ecoles/form.html', {'auto_ecole': ae})


# ─── ADMIN : EXAMINATEURS ──────────────────────────────────────────────────────

@login_required
@role_required('admin')
def liste_examinateurs(request):
    examinateurs = Examinateur.objects.all()
    return render(request, 'core/admin/examinateurs/liste.html', {'examinateurs': examinateurs})


@login_required
@role_required('admin')
def creer_examinateur(request):
    if request.method == 'POST':
        try:
            ex = Examinateur.objects.create(
                nom=request.POST['nom'].upper(),
                prenom=request.POST.get('prenom', ''),
                telephone=request.POST.get('telephone', ''),
            )
            messages.success(request, f"Examinateur {ex} créé.")
            return redirect('liste_examinateurs')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return render(request, 'core/admin/examinateurs/form.html')


@login_required
@role_required('admin')
def toggle_examinateur(request, pk):
    ex = get_object_or_404(Examinateur, pk=pk)
    ex.actif = not ex.actif
    ex.save()
    messages.success(request, f"Examinateur {'activé' if ex.actif else 'désactivé'}.")
    return redirect('liste_examinateurs')


# ─── ADMIN : CATÉGORIES DE PERMIS ──────────────────────────────────────────────

@login_required
@role_required('admin')
def liste_categories(request):
    categories = CategoriePermis.objects.all()
    return render(request, 'core/admin/categories/liste.html', {'categories': categories})


@login_required
@role_required('admin')
def creer_categorie(request):
    if request.method == 'POST':
        try:
            code = request.POST['code'].strip().upper()
            if CategoriePermis.objects.filter(code=code).exists():
                messages.error(request, f"La catégorie {code} existe déjà.")
                return render(request, 'core/admin/categories/form.html')
            ordre_max = CategoriePermis.objects.count()
            cat = CategoriePermis.objects.create(
                code=code,
                libelle=request.POST.get('libelle', ''),
                ordre=ordre_max,
            )
            messages.success(request, f"Catégorie {cat.code} créée.")
            return redirect('liste_categories')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return render(request, 'core/admin/categories/form.html')


@login_required
@role_required('admin')
def toggle_categorie(request, pk):
    cat = get_object_or_404(CategoriePermis, pk=pk)
    cat.actif = not cat.actif
    cat.save()
    messages.success(request, f"Catégorie {cat.code} {'activée' if cat.actif else 'désactivée'}.")
    return redirect('liste_categories')


# ─── ADMIN : AUDIT ─────────────────────────────────────────────────────────────

@login_required
@role_required('admin')
def journal_audit(request):
    journaux = JournalAudit.objects.select_related('utilisateur').all()[:200]
    return render(request, 'core/admin/audit.html', {'journaux': journaux})


# ─── AUTOCOMPLETE ──────────────────────────────────────────────────────────────

@login_required
def autocomplete_auto_ecole(request):
    q = request.GET.get('q', '')
    resultats = AutoEcole.objects.filter(
        nom__icontains=q, actif=True).values('id', 'nom')[:10]
    return JsonResponse(list(resultats), safe=False)


# ─── ADMIN : PARAMÈTRES IMPRESSION (éditeur glisser-déposer) ──────────────────

@login_required
@role_required('admin')
def parametres_impression(request):
    """Liste des types de fiches à configurer."""
    types = ParametreImpression.TYPE_FICHE_CHOICES
    return render(request, 'core/admin/parametres.html', {'types': types})


@login_required
@role_required('admin')
def editeur_position(request, type_fiche):
    """Éditeur visuel : place chaque champ par glisser-déposer sur un aperçu A4."""
    from .models import CHAMPS_PAR_FICHE

    if type_fiche not in dict(ParametreImpression.TYPE_FICHE_CHOICES):
        messages.error(request, "Type de fiche inconnu.")
        return redirect('parametres_impression')

    champs_definis = CHAMPS_PAR_FICHE.get(type_fiche, [])
    # S'assurer que chaque champ a une position en base
    for champ, label in champs_definis:
        ParametreImpression.objects.get_or_create(
            type_fiche=type_fiche, champ=champ,
            defaults={'label': label, 'x_mm': 20, 'y_mm': 20}
        )
    positions = ParametreImpression.objects.filter(type_fiche=type_fiche)

    return render(request, 'core/admin/editeur_position.html', {
        'type_fiche': type_fiche,
        'label': dict(ParametreImpression.TYPE_FICHE_CHOICES).get(type_fiche, type_fiche),
        'positions': positions,
    })


@login_required
@role_required('admin')
def sauvegarder_positions(request, type_fiche):
    """Endpoint AJAX appelé après chaque glisser-déposer pour sauvegarder la position."""
    if request.method == 'POST':
        try:
            champ = request.POST.get('champ')
            x_mm = float(request.POST.get('x_mm', 0))
            y_mm = float(request.POST.get('y_mm', 0))
            obj = ParametreImpression.objects.get(type_fiche=type_fiche, champ=champ)
            obj.x_mm = round(x_mm, 1)
            obj.y_mm = round(y_mm, 1)
            obj.save()
            return JsonResponse({'ok': True, 'x_mm': obj.x_mm, 'y_mm': obj.y_mm})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    return JsonResponse({'ok': False}, status=405)


@login_required
@role_required('admin')
def modifier_champ_position(request, pk):
    """Modifie taille de police / visibilité / largeur d'un champ (formulaire classique)."""
    obj = get_object_or_404(ParametreImpression, pk=pk)
    if request.method == 'POST':
        try:
            obj.taille_police = int(request.POST.get('taille_police', obj.taille_police) or obj.taille_police)
            obj.visible = request.POST.get('visible') == '1'
            largeur = request.POST.get('largeur_mm', '').strip()
            if largeur:
                obj.largeur_mm = float(largeur.replace(',', '.'))
            obj.save()
            messages.success(request, f"Champ « {obj.label} » mis à jour.")
        except (ValueError, TypeError):
            messages.error(request, "Valeurs invalides.")
    return redirect('editeur_position', type_fiche=obj.type_fiche)


@login_required
@role_required('admin')
def test_impression(request, type_fiche):
    """Affiche une fiche de test réelle avec les positions actuelles, pour vérifier sur papier."""
    from .models import CHAMPS_PAR_FICHE
    positions = ParametreImpression.objects.filter(type_fiche=type_fiche, visible=True)
    return render(request, 'core/admin/test_impression.html', {
        'type_fiche': type_fiche,
        'positions': positions,
        'label': dict(ParametreImpression.TYPE_FICHE_CHOICES).get(type_fiche, type_fiche),
    })


# ─── ADMIN : RAPPORTS AVANCÉS ──────────────────────────────────────────────────

@login_required
@role_required('admin')
def rapports_admin(request):
    date_debut = request.GET.get('date_debut', '').strip()
    date_fin = request.GET.get('date_fin', '').strip()
    categorie = request.GET.get('categorie', '').strip()
    auto_ecole = request.GET.get('auto_ecole', '').strip()
    type_examen = request.GET.get('type_examen', 'code').strip() or 'code'

    a_filtre = any([date_debut, date_fin, categorie, auto_ecole])

    stats = None
    if a_filtre:
        Model = ExamenCode if type_examen == 'code' else ExamenConduite
        qs = Model.objects.select_related('candidat', 'candidat__auto_ecole')

        if date_debut:
            qs = qs.filter(date_examen__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_examen__lte=date_fin)
        if categorie:
            qs = qs.filter(candidat__categorie=categorie)
        if auto_ecole:
            qs = qs.filter(candidat__auto_ecole_id=auto_ecole)

        stats = {
            'total': qs.count(),
            'aptes': qs.filter(resultat='APTE').count(),
            'inaptes': qs.filter(resultat='INAPTE').count(),
            'absents': qs.filter(resultat='ABSENT').count(),
            'reprogrammes': qs.filter(resultat='REPROGRAMME').count() if type_examen == 'conduite' else 0,
            'en_attente': qs.filter(resultat='EN_ATTENTE').count(),
            'par_categorie': qs.values('candidat__categorie').annotate(
                total=Count('id'),
                aptes=Count('id', filter=Q(resultat='APTE')),
                inaptes=Count('id', filter=Q(resultat='INAPTE')),
                absents=Count('id', filter=Q(resultat='ABSENT')),
            ).order_by('candidat__categorie'),
            'par_auto_ecole': qs.values('candidat__auto_ecole__nom').annotate(
                total=Count('id'),
                aptes=Count('id', filter=Q(resultat='APTE')),
                inaptes=Count('id', filter=Q(resultat='INAPTE')),
                absents=Count('id', filter=Q(resultat='ABSENT')),
            ).order_by('-total'),
        }

    return render(request, 'core/admin/rapports_admin.html', {
        'stats': stats, 'a_filtre': a_filtre,
        'date_debut': date_debut, 'date_fin': date_fin,
        'categorie': categorie, 'auto_ecole': auto_ecole, 'type_examen': type_examen,
        'categories': [(c.code, c.code) for c in CategoriePermis.objects.filter(actif=True)],
        'auto_ecoles': AutoEcole.objects.order_by('nom'),
    })


# ─── PORTAIL CANDIDAT (public) ─────────────────────────────────────────────────

def candidat_connexion(request):
    """Connexion candidat par numéro de dossier uniquement."""
    if request.session.get('candidat_id'):
        return redirect('candidat_resultats')
    if request.method == 'POST':
        numero = request.POST.get('numero_dossier', '').strip()
        try:
            candidat = Candidat.objects.get(numero_dossier=numero)
            request.session['candidat_id'] = candidat.pk
            return redirect('candidat_resultats')
        except Candidat.DoesNotExist:
            messages.error(request, "Aucun dossier trouvé avec ce numéro.")
    return render(request, 'core/candidat_portal/connexion.html')


def candidat_deconnexion(request):
    request.session.pop('candidat_id', None)
    return redirect('candidat_connexion')


def candidat_resultats(request):
    candidat_id = request.session.get('candidat_id')
    if not candidat_id:
        return redirect('candidat_connexion')
    candidat = get_object_or_404(Candidat, pk=candidat_id)
    return render(request, 'core/candidat_portal/resultats.html', {
        'candidat': candidat,
    })


# ─── MODIFIER CANDIDAT ─────────────────────────────────────────────────────────

@login_required
def modifier_candidat(request, pk):
    candidat = get_object_or_404(Candidat, pk=pk)
    if request.method == 'POST':
        try:
            candidat.nom = request.POST['nom'].upper()
            candidat.prenom = request.POST['prenom']
            candidat.date_naissance = request.POST['date_naissance']
            candidat.lieu_naissance = request.POST['lieu_naissance']
            candidat.sexe = request.POST['sexe']
            candidat.telephone = request.POST.get('telephone', '')
            candidat.categorie = request.POST['categorie']
            ae_id = request.POST.get('auto_ecole')
            if ae_id:
                candidat.auto_ecole_id = ae_id
            candidat.save()
            JournalAudit.objects.create(
                utilisateur=request.user, action='MODIFICATION',
                modele='Candidat', objet_id=candidat.numero_dossier,
                description=f'Candidat modifié : {candidat.nom} {candidat.prenom}',
                adresse_ip=get_client_ip(request))
            messages.success(request, f"Dossier {candidat.numero_dossier} mis à jour.")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return redirect('detail_candidat', pk=pk)


# ─── FICHES IMPRESSION (données seulement - papier pré-imprimé) ────────────────

def _valeurs_fiche_controle(candidat):
    return {
        'numero_permis': candidat.numero_permis or candidat.numero_dossier,
        'nom_complet': f"{candidat.nom.upper()} {candidat.prenom.upper()}",
        'nom': candidat.nom.upper(),
        'prenom': candidat.prenom,
        'date_lieu_naissance': f"{candidat.date_naissance.strftime('%d/%m/%Y')}  {candidat.lieu_naissance.upper()}",
        'auto_ecole': candidat.auto_ecole.nom,
    }


def _valeurs_fiche_examen(candidat, examen, aujourd_hui):
    return {
        'date_jour': aujourd_hui.strftime('%d/%m/%Y'),
        'date_examen': examen.date_examen.strftime('%d/%m/%Y') if examen else '—',
        'numero_examen': str(examen.pk) if examen else '—',
        'nom': candidat.nom.upper(),
        'prenom': candidat.prenom,
        'numero_dossier': candidat.numero_dossier,
        'auto_ecole': candidat.auto_ecole.nom,
    }


@login_required
def imprimer_fiche_controle(request, pk):
    """Fiche permis de conduire - contrôle (papier pré-imprimé, positions configurées)."""
    candidat = get_object_or_404(Candidat, pk=pk)
    positions = ParametreImpression.objects.filter(type_fiche='fiche_controle', visible=True)
    valeurs = _valeurs_fiche_controle(candidat)
    return render(request, 'core/impressions/fiche_controle.html', {
        'candidat': candidat,
        'positions': positions,
        'valeurs': valeurs,
        'aujourd_hui': date.today(),
    })


@login_required
def fiche_examen_code(request):
    """Fiche examen code - positions configurées par l'admin."""
    numero = request.GET.get('numero', '').strip()
    candidat = None
    examen = None
    valeurs = {}
    positions = ParametreImpression.objects.filter(type_fiche='fiche_examen_code', visible=True)
    if numero:
        candidat = Candidat.objects.filter(numero_dossier=numero).first()
        if candidat:
            examen = candidat.dernier_examen_code
            valeurs = _valeurs_fiche_examen(candidat, examen, date.today())
    return render(request, 'core/impressions/fiche_examen_code.html', {
        'candidat': candidat,
        'examen': examen,
        'numero': numero,
        'positions': positions,
        'valeurs': valeurs,
        'aujourd_hui': date.today(),
    })


@login_required
def fiche_examen_conduite(request):
    """Fiche examen conduite - positions configurées par l'admin."""
    numero = request.GET.get('numero', '').strip()
    candidat = None
    examen = None
    valeurs = {}
    positions = ParametreImpression.objects.filter(type_fiche='fiche_examen_conduite', visible=True)
    if numero:
        candidat = Candidat.objects.filter(numero_dossier=numero).first()
        if candidat:
            examen = candidat.dernier_examen_conduite
            valeurs = _valeurs_fiche_examen(candidat, examen, date.today())
    return render(request, 'core/impressions/fiche_examen_conduite.html', {
        'candidat': candidat,
        'examen': examen,
        'numero': numero,
        'positions': positions,
        'valeurs': valeurs,
        'aujourd_hui': date.today(),
    })


# ─── PROGRAMMER CODE DEPUIS DETAIL (ancien dossier sans date) ─────────────────

@login_required
def programmer_code(request, pk):
    """Ajoute un examen code à la date choisie (pour anciens dossiers sans code programmé)."""
    candidat = get_object_or_404(Candidat, pk=pk)
    if request.method == 'POST':
        nouvelle_date = request.POST.get('date_code', '').strip()
        if not nouvelle_date:
            messages.error(request, "Veuillez choisir une date.")
            return redirect('detail_candidat', pk=pk)
        # Bloquer si un examen code EN_ATTENTE existe déjà
        deja = ExamenCode.objects.filter(candidat=candidat, resultat='EN_ATTENTE').exists()
        if deja:
            messages.error(request, "Un examen code est déjà programmé en attente.")
            return redirect('detail_candidat', pk=pk)
        ExamenCode.objects.create(candidat=candidat, date_examen=nouvelle_date)
        from datetime import date as date_type
        d = date_type.fromisoformat(nouvelle_date)
        messages.success(request, f"Code programmé le {d.strftime('%d/%m/%Y')}.")
    return redirect('detail_candidat', pk=pk)


# ─── REPROGRAMMER CODE (INAPTE) ───────────────────────────────────────────────

@login_required  
def reprogrammer_code(request, pk):
    """Reprogramme le code après INAPTE ou ABSENT."""
    candidat = get_object_or_404(Candidat, pk=pk)
    if request.method == 'POST':
        nouvelle_date = request.POST.get('date_reprog_code', '').strip()
        if not nouvelle_date:
            messages.error(request, "Veuillez choisir une date.")
            return redirect('detail_candidat', pk=pk)
        dernier = candidat.dernier_examen_code
        if dernier and dernier.resultat == 'INAPTE':
            from datetime import date as date_type
            d = date_type.fromisoformat(nouvelle_date)
            date_min = dernier.date_examen + __import__('datetime').timedelta(days=7)
            if d < date_min:
                messages.error(request, f"Après un échec, le candidat ne peut repasser qu'à partir du {date_min.strftime('%d/%m/%Y')} (7 jours minimum).")
                return redirect('detail_candidat', pk=pk)
        ExamenCode.objects.create(candidat=candidat, date_examen=nouvelle_date)
        from datetime import date as date_type
        d = date_type.fromisoformat(nouvelle_date)
        messages.success(request, f"Code reprogrammé le {d.strftime('%d/%m/%Y')}.")
    return redirect('detail_candidat', pk=pk)
