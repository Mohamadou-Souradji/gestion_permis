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
    AutoEcole, ProfilAgent, Candidat, ExamenCode, ExamenConduite,
    JournalAudit, prochain_jour_ouvre, generer_numero_permis
)
from .decorators import role_required


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


# ─── AUTHENTIFICATION ──────────────────────────────────────────────────────────

def connexion(request):
    if request.user.is_authenticated:
        return redirect('tableau_de_bord')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            profil = getattr(user, 'profil', None)
            if profil and profil.actif:
                login(request, user)
                JournalAudit.objects.create(
                    utilisateur=user, action='CONNEXION',
                    description=f'Connexion depuis {get_client_ip(request)}',
                    adresse_ip=get_client_ip(request)
                )
                return redirect('tableau_de_bord')
            else:
                messages.error(request, "Votre compte est désactivé. Contactez l'administrateur.")
        else:
            messages.error(request, "Identifiant ou mot de passe incorrect.")
    return render(request, 'core/connexion.html')


@login_required
def deconnexion(request):
    JournalAudit.objects.create(
        utilisateur=request.user, action='DECONNEXION',
        description='Déconnexion',
        adresse_ip=get_client_ip(request)
    )
    logout(request)
    return redirect('connexion')


# ─── TABLEAU DE BORD ───────────────────────────────────────────────────────────

@login_required
def tableau_de_bord(request):
    aujourd_hui = date.today()
    profil = getattr(request.user, 'profil', None)
    role = profil.role if profil else 'direction'

    ctx = {
        'total_candidats': Candidat.objects.count(),
        'examens_aujourd_hui': ExamenCode.objects.filter(
            date_examen=aujourd_hui, resultat='EN_ATTENTE').count() +
            ExamenConduite.objects.filter(
            date_examen=aujourd_hui, resultat='EN_ATTENTE').count(),
        'aptes_code': ExamenCode.objects.filter(resultat='APTE').values('candidat').distinct().count(),
        'permis_delivres': ExamenConduite.objects.filter(resultat='APTE').count(),
        'examens_code_aujourd_hui': ExamenCode.objects.filter(
            date_examen=aujourd_hui).select_related('candidat', 'candidat__auto_ecole'),
        'examens_conduite_aujourd_hui': ExamenConduite.objects.filter(
            date_examen=aujourd_hui).select_related('candidat', 'candidat__auto_ecole'),
        'role': role,
    }
    return render(request, 'core/tableau_de_bord.html', ctx)


# ─── GESTION CANDIDATS ─────────────────────────────────────────────────────────

@login_required
def liste_candidats(request):
    qs = Candidat.objects.select_related('auto_ecole').all()
    q = request.GET.get('q', '')
    categorie = request.GET.get('categorie', '')
    if q:
        qs = qs.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) |
            Q(numero_dossier__icontains=q) | Q(numero_cni__icontains=q)
        )
    if categorie:
        qs = qs.filter(categorie=categorie)
    return render(request, 'core/candidats/liste.html', {
        'candidats': qs.order_by('-date_inscription'),
        'q': q,
        'categorie': categorie,
        'categories': Candidat.CATEGORIE_CHOICES,
    })


@login_required
def creer_candidat(request):
    if request.method == 'POST':
        try:
            auto_ecole = AutoEcole.objects.get(id=request.POST['auto_ecole'])
            candidat = Candidat.objects.create(
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
            # Programmation automatique code J+1 ouvré
            date_code = prochain_jour_ouvre(date.today())
            ExamenCode.objects.create(candidat=candidat, date_examen=date_code)
            JournalAudit.objects.create(
                utilisateur=request.user, action='CREATION',
                modele='Candidat', objet_id=candidat.numero_dossier,
                description=f'Candidat créé : {candidat.nom} {candidat.prenom}',
                adresse_ip=get_client_ip(request)
            )
            messages.success(request, f"Dossier {candidat.numero_dossier} créé. Examen code programmé le {date_code.strftime('%d/%m/%Y')}.")
            return redirect('detail_candidat', pk=candidat.pk)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
    return render(request, 'core/candidats/form.html', {
        'auto_ecoles': AutoEcole.objects.filter(actif=True).order_by('nom'),
        'categories': Candidat.CATEGORIE_CHOICES,
        'sexes': Candidat.SEXE_CHOICES,
    })


@login_required
def detail_candidat(request, pk):
    candidat = get_object_or_404(Candidat, pk=pk)
    return render(request, 'core/candidats/detail.html', {'candidat': candidat})


# ─── EXAMENS ───────────────────────────────────────────────────────────────────

@login_required
def examens_code_jour(request):
    jour = request.GET.get('date', date.today().isoformat())
    try:
        jour_dt = date.fromisoformat(jour)
    except ValueError:
        jour_dt = date.today()
    codes = ExamenCode.objects.filter(
        date_examen=jour_dt).select_related('candidat', 'candidat__auto_ecole')
    return render(request, 'core/examens/jour.html', {
        'type_examen': 'code',
        'examens': codes,
        'jour': jour_dt, 'aujourd_hui': date.today(),
    })


@login_required
def examens_conduite_jour(request):
    jour = request.GET.get('date', date.today().isoformat())
    try:
        jour_dt = date.fromisoformat(jour)
    except ValueError:
        jour_dt = date.today()
    conduites = ExamenConduite.objects.filter(
        date_examen=jour_dt).select_related('candidat', 'candidat__auto_ecole')
    return render(request, 'core/examens/jour.html', {
        'type_examen': 'conduite',
        'examens': conduites,
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
            note = int(request.POST.get('note', 0))
            examen.note = note
            examen.determiner_resultat()
        examen.date_saisie = timezone.now()
        examen.saisi_par = request.user
        examen.save()
        # Si APTE → programmer conduite
        if examen.resultat == 'APTE':
            date_conduite = prochain_jour_ouvre(date.today())
            ExamenConduite.objects.create(
                candidat=examen.candidat, date_examen=date_conduite)
            messages.success(request, f"Apte au code. Conduite programmée le {date_conduite.strftime('%d/%m/%Y')}.")
        else:
            messages.info(request, f"Résultat enregistré : {examen.get_resultat_display()}")
        JournalAudit.objects.create(
            utilisateur=request.user, action='SAISIE_RESULTAT',
            modele='ExamenCode', objet_id=str(examen.pk),
            description=f'Résultat code {examen.candidat.numero_dossier} : {examen.resultat}',
            adresse_ip=get_client_ip(request)
        )
        return redirect('examens_code_jour')
    return render(request, 'core/examens/saisie_code.html', {'examen': examen})


@login_required
def saisir_resultat_conduite(request, pk):
    examen = get_object_or_404(ExamenConduite, pk=pk)
    if request.method == 'POST':
        absent = request.POST.get('absent') == '1'
        if absent:
            examen.resultat = 'ABSENT'
            examen.note = None
        else:
            note = int(request.POST.get('note', 0))
            examen.note = note
            examen.determiner_resultat()
        examen.date_saisie = timezone.now()
        examen.saisi_par = request.user
        examen.save()
        if examen.resultat == 'APTE':
            messages.success(request, "Candidat apte. Attestation disponible.")
        else:
            messages.info(request, f"Résultat enregistré : {examen.get_resultat_display()}")
        JournalAudit.objects.create(
            utilisateur=request.user, action='SAISIE_RESULTAT',
            modele='ExamenConduite', objet_id=str(examen.pk),
            description=f'Résultat conduite {examen.candidat.numero_dossier} : {examen.resultat}',
            adresse_ip=get_client_ip(request)
        )
        return redirect('examens_conduite_jour')
    return render(request, 'core/examens/saisie_conduite.html', {'examen': examen})


@login_required
def reprogrammer_candidat(request, pk, type_examen):
    candidat = get_object_or_404(Candidat, pk=pk)
    if type_examen == 'code':
        dernier = candidat.dernier_examen_code
        if dernier:
            nouvelle_date = dernier.prochaine_date_programmable()
            if nouvelle_date:
                ExamenCode.objects.create(candidat=candidat, date_examen=nouvelle_date)
                messages.success(request, f"Reprogrammé au code le {nouvelle_date.strftime('%d/%m/%Y')}.")
    elif type_examen == 'conduite':
        dernier = candidat.dernier_examen_conduite
        if dernier:
            nouvelle_date = dernier.prochaine_date_programmable()
            if nouvelle_date:
                ExamenConduite.objects.create(candidat=candidat, date_examen=nouvelle_date)
                messages.success(request, f"Reprogrammé à la conduite le {nouvelle_date.strftime('%d/%m/%Y')}.")
    return redirect('detail_candidat', pk=pk)


@login_required
def imprimer_liste_examens(request, type_examen):
    """Imprime la liste du jour triée : Aptes > Inaptes > Absents > En attente."""
    jour_str = request.GET.get('date', date.today().isoformat())
    try:
        jour_dt = date.fromisoformat(jour_str)
    except ValueError:
        jour_dt = date.today()

    ordre = {'APTE': 0, 'INAPTE': 1, 'ABSENT': 2, 'EN_ATTENTE': 3}

    if type_examen == 'code':
        examens = list(ExamenCode.objects.filter(
            date_examen=jour_dt
        ).select_related('candidat', 'candidat__auto_ecole'))
    else:
        examens = list(ExamenConduite.objects.filter(
            date_examen=jour_dt
        ).select_related('candidat', 'candidat__auto_ecole'))

    examens.sort(key=lambda e: ordre.get(e.resultat, 9))

    return render(request, 'core/examens/imprimer_liste.html', {
        'examens': examens,
        'type_examen': type_examen,
        'jour': jour_dt,
    })


# ─── ABSENTS ───────────────────────────────────────────────────────────────────

@login_required
def liste_absents(request):
    nom = request.GET.get('nom', '').strip()
    auto_ecole = request.GET.get('auto_ecole', '').strip()
    categorie = request.GET.get('categorie', '').strip()
    type_examen = request.GET.get('type_examen', '').strip()

    absents_code = ExamenCode.objects.filter(
        resultat='ABSENT'
    ).select_related('candidat', 'candidat__auto_ecole').order_by('-date_examen')

    absents_conduite = ExamenConduite.objects.filter(
        resultat='ABSENT'
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
        'absents_code': absents_code,
        'absents_conduite': absents_conduite,
        'nom': nom,
        'auto_ecole': auto_ecole,
        'categorie': categorie,
        'type_examen': type_examen,
        'auto_ecoles': AutoEcole.objects.order_by('nom'),
        'categories': Candidat.CATEGORIE_CHOICES,
    })


@login_required
def programmer_absent(request, pk, type_examen):
    """Reprogramme un absent à une date choisie."""
    if request.method == 'POST':
        nouvelle_date_str = request.POST.get('nouvelle_date', '')
        try:
            nouvelle_date = date.fromisoformat(nouvelle_date_str)
        except ValueError:
            messages.error(request, "Date invalide.")
            return redirect('liste_absents')

        if type_examen == 'code':
            examen = get_object_or_404(ExamenCode, pk=pk, resultat='ABSENT')
            ExamenCode.objects.create(
                candidat=examen.candidat, date_examen=nouvelle_date)
            messages.success(
                request,
                f"{examen.candidat.nom} {examen.candidat.prenom} reprogrammé au code le {nouvelle_date.strftime('%d/%m/%Y')}.")
        elif type_examen == 'conduite':
            examen = get_object_or_404(ExamenConduite, pk=pk, resultat='ABSENT')
            ExamenConduite.objects.create(
                candidat=examen.candidat, date_examen=nouvelle_date)
            messages.success(
                request,
                f"{examen.candidat.nom} {examen.candidat.prenom} reprogrammé à la conduite le {nouvelle_date.strftime('%d/%m/%Y')}.")
        JournalAudit.objects.create(
            utilisateur=request.user, action='MODIFICATION',
            description=f'Absent reprogrammé {type_examen} le {nouvelle_date}',
            adresse_ip=get_client_ip(request)
        )
    return redirect('liste_absents')


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
                user=user,
                role=request.POST['role'],
                telephone=request.POST.get('telephone', ''),
            )
            JournalAudit.objects.create(
                utilisateur=request.user, action='CREATION',
                modele='Agent', objet_id=str(user.pk),
                description=f'Agent créé : {user.get_full_name()}',
                adresse_ip=get_client_ip(request)
            )
            messages.success(request, f"Compte agent créé pour {user.get_full_name()}.")
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
    etat = "activé" if profil.actif else "désactivé"
    messages.success(request, f"Compte {profil.user.get_full_name()} {etat}.")
    return redirect('liste_agents')


# ─── ADMIN : AUTO-ÉCOLES ───────────────────────────────────────────────────────

@login_required
@role_required('admin')
def liste_auto_ecoles(request):
    q = request.GET.get('q', '')
    qs = AutoEcole.objects.annotate(nb_candidats=Count('candidats'))
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(responsable__icontains=q))
    return render(request, 'core/admin/auto_ecoles/liste.html', {
        'auto_ecoles': qs, 'q': q,
    })


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


# ─── ADMIN : AUDIT ─────────────────────────────────────────────────────────────

@login_required
@role_required('admin')
def journal_audit(request):
    qs = JournalAudit.objects.select_related('utilisateur').all()[:200]
    return render(request, 'core/admin/audit.html', {'journaux': qs})


# ─── AUTOCOMPLETE ──────────────────────────────────────────────────────────────

@login_required
def autocomplete_auto_ecole(request):
    q = request.GET.get('q', '')
    resultats = AutoEcole.objects.filter(
        nom__icontains=q, actif=True
    ).values('id', 'nom')[:10]
    return JsonResponse(list(resultats), safe=False)


# ─── RAPPORTS ──────────────────────────────────────────────────────────────────

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
        'candidats': candidats,
        'a_filtre': a_filtre,
        'nom': nom,
        'numero_dossier': numero_dossier,
        'auto_ecole': auto_ecole,
        'categorie': categorie,
        'auto_ecoles': AutoEcole.objects.order_by('nom'),
        'categories': Candidat.CATEGORIE_CHOICES,
    })


@login_required
def imprimer_attestation(request, pk):
    candidat = get_object_or_404(Candidat, pk=pk)
    if not candidat.est_apte_complet:
        messages.error(request, "Ce candidat n'a pas validé les deux examens (code et conduite).")
        return redirect('liste_attestations')

    if not candidat.numero_permis:
        candidat.numero_permis = generer_numero_permis()
        candidat.save()

    examen_conduite = candidat.dernier_examen_conduite
    date_delivrance = examen_conduite.date_examen if examen_conduite else date.today()
    date_validite = date_delivrance + timedelta(days=30)

    return render(request, 'core/attestations/imprimer.html', {
        'candidat': candidat,
        'date_delivrance': date_delivrance,
        'date_validite': date_validite,
        'aujourd_hui': date.today(),
    })


@login_required
def rapports(request):
    stats = {
        'par_categorie': Candidat.objects.values('categorie').annotate(total=Count('id')),
        'par_auto_ecole': Candidat.objects.values(
            'auto_ecole__nom').annotate(total=Count('id')).order_by('-total')[:10],
        'taux_reussite_code': ExamenCode.objects.exclude(
            resultat='EN_ATTENTE').aggregate(
            total=Count('id'),
            aptes=Count('id', filter=Q(resultat='APTE'))
        ),
        'taux_reussite_conduite': ExamenConduite.objects.exclude(
            resultat='EN_ATTENTE').aggregate(
            total=Count('id'),
            aptes=Count('id', filter=Q(resultat='APTE'))
        ),
    }
    return render(request, 'core/rapports.html', {'stats': stats})
