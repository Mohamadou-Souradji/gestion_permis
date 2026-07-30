# ═══════════════════════════════════════════════════════════════════════════
# VIEWS IMPRESSION - Traçabilité complète (20/07/2026)
# ═══════════════════════════════════════════════════════════════════════════

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db import models
import hashlib
import json
import csv
from datetime import date
import qrcode
from io import BytesIO
import base64

from .models import (
    Candidat, ParametreImpressionAugmente, JournalImpression,
    PreferenceImpressionAgent, ModeleImpression, Attestation,
    ProfilAgent
)


def get_client_ip(request):
    """Récupère l'adresse IP réelle du client"""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


def get_user_agent(request):
    """Récupère le user-agent du client"""
    return request.META.get('HTTP_USER_AGENT', '')


def enregistrer_impression(request, type_fiche, candidat=None,
                          statut='succes', message_erreur='', parametres=None):
    """
    FONCTION CLEF: Enregistre CHAQUE impression dans le journal d'audit.
    À appeler après chaque génération d'impression.
    """
    try:
        agent = None
        if hasattr(request.user, 'profil'):
            try:
                agent = request.user.profil
            except:
                pass
        
        hash_doc = hashlib.sha256(
            f"{type_fiche}{candidat}{timezone.now()}".encode()
        ).hexdigest()
        
        impression = JournalImpression.objects.create(
            agent=agent,
            utilisateur=request.user,
            type_fiche=type_fiche,
            candidat=candidat,
            statut=statut,
            message_erreur=message_erreur,
            adresse_ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            parametres_appliques=parametres or {},
            hash_document=hash_doc,
        )
        return impression
    except Exception as e:
        print(f"⚠️ Erreur enregistrement impression: {e}")
        return None


def generer_qr_code(donnees):
    """Génère un QR code en base64 (data URI)"""
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(donnees)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"⚠️ Erreur génération QR: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# PARAMÈTRES D'IMPRESSION
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def parametres_impression(request):
    """Page d'administration des paramètres d'impression"""
    if not hasattr(request.user, 'profil') or request.user.profil.role != 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('tableau_de_bord')
    
    types = ParametreImpressionAugmente.TYPE_FICHE_CHOICES
    modeles = ModeleImpression.objects.all()
    
    ctx = {
        'types': types,
        'modeles': modeles,
        'nombre_impressions': JournalImpression.objects.count(),
        'impressions_24h': JournalImpression.objects.filter(
            date_impression__gte=timezone.now() - timezone.timedelta(days=1)
        ).count(),
    }
    return render(request, 'core/admin/parametres_impression.html', ctx)


@login_required
@require_http_methods(["GET"])
def editeur_position(request, type_fiche):
    """Éditeur visual des positions de champs (drag-drop)"""
    if not hasattr(request.user, 'profil') or request.user.profil.role != 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('tableau_de_bord')
    
    if type_fiche not in dict(ParametreImpressionAugmente.TYPE_FICHE_CHOICES):
        messages.error(request, "Type de fiche invalide.")
        return redirect('parametres_impression')
    
    positions = ParametreImpressionAugmente.objects.filter(
        type_fiche=type_fiche, visible=True
    )
    
    ctx = {
        'type_fiche': type_fiche,
        'label': dict(ParametreImpressionAugmente.TYPE_FICHE_CHOICES).get(type_fiche),
        'positions': positions,
    }
    return render(request, 'core/admin/editeur_position.html', ctx)


@login_required
@require_http_methods(["POST"])
def sauvegarder_positions(request, type_fiche):
    """Sauvegarde les positions via AJAX (drag-drop)"""
    if not hasattr(request.user, 'profil') or request.user.profil.role != 'admin':
        return JsonResponse({'erreur': 'Accès non autorisé'}, status=403)
    
    try:
        champ = request.POST.get('champ')
        x_mm = float(request.POST.get('x_mm', 20))
        y_mm = float(request.POST.get('y_mm', 20))
        
        obj = ParametreImpressionAugmente.objects.get(
            type_fiche=type_fiche, champ=champ
        )
        obj.x_mm = x_mm
        obj.y_mm = y_mm
        obj.modifie_par = request.user
        obj.save()
        
        return JsonResponse({
            'succes': True,
            'message': f'Position {champ} sauvegardée',
            'position': {'x': x_mm, 'y': y_mm}
        })
    except Exception as e:
        return JsonResponse({'erreur': str(e)}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
# IMPRESSIONS
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def imprimer_attestation(request, pk):
    """Impression d'attestation avec QR code"""
    attestation = get_object_or_404(Attestation, pk=pk)
    candidat = attestation.candidat
    positions = ParametreImpressionAugmente.objects.filter(
        type_fiche='attestation', visible=True
    )
    
    donnees_qr = f"{attestation.numero_attestation}|{attestation.cle_verification}"
    qr_data_uri = generer_qr_code(donnees_qr)
    
    def _valeurs():
        return {
            'frais': attestation.frais_percus,
            'nom': candidat.nom.upper(),
            'prenom': candidat.prenom,
            'numero_dossier_categorie': f"{candidat.numero_dossier}",
            'date_validite': timezone.now().strftime('%d/%m/%Y'),
            'qr_code': qr_data_uri,
        }
    
    valeurs = _valeurs()
    
    parametres = {
        'positions': [p.to_dict() for p in positions],
        'attestation': attestation.numero_attestation,
        'qr_present': bool(qr_data_uri),
    }
    
    impression = enregistrer_impression(
        request,
        type_fiche='attestation',
        candidat=candidat,
        parametres=parametres
    )
    
    return render(request, 'core/attestations/imprimer.html', {
        'attestation': attestation,
        'candidat': candidat,
        'positions': positions,
        'valeurs': valeurs,
        'qr_data_uri': qr_data_uri,
        'impression_id': impression.pk if impression else None,
    })


# ═══════════════════════════════════════════════════════════════════════════
# RAPPORT D'IMPRESSIONS (AUDIT)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def rapport_impressions(request):
    """Rapport complet des impressions"""
    if not hasattr(request.user, 'profil') or request.user.profil.role != 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('tableau_de_bord')
    
    agent_id = request.GET.get('agent')
    type_fiche = request.GET.get('type_fiche')
    statut = request.GET.get('statut')
    
    impressions = JournalImpression.objects.select_related('agent', 'candidat')
    
    if agent_id:
        impressions = impressions.filter(agent_id=agent_id)
    if type_fiche:
        impressions = impressions.filter(type_fiche=type_fiche)
    if statut:
        impressions = impressions.filter(statut=statut)
    
    stats = {
        'total': impressions.count(),
        'reussites': impressions.filter(statut='succes').count(),
        'erreurs': impressions.filter(statut='erreur').count(),
    }
    
    ctx = {
        'impressions': impressions[:1000],
        'stats': stats,
        'agents': ProfilAgent.objects.select_related('user').all(),
    }
    return render(request, 'core/admin/rapport_impressions.html', ctx)


@login_required
def export_journal_impression(request):
    """Export du journal d'impression en CSV"""
    if not hasattr(request.user, 'profil') or request.user.profil.role != 'admin':
        return JsonResponse({'erreur': 'Non autorisé'}, status=403)
    
    impressions = JournalImpression.objects.select_related(
        'agent', 'candidat', 'utilisateur'
    ).all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="journal_impressions.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Agent', 'Utilisateur', 'Type Document', 'Candidat',
        'Copies', 'Imprimante', 'Statut', 'IP', 'Details'
    ])
    
    for imp in impressions:
        writer.writerow([
            imp.date_impression.strftime('%d/%m/%Y %H:%M:%S'),
            str(imp.agent) if imp.agent else 'N/A',
            imp.utilisateur.get_full_name() if imp.utilisateur else 'N/A',
            imp.get_type_fiche_display(),
            f"{imp.candidat.numero_dossier}" if imp.candidat else 'N/A',
            imp.nombre_copies,
            imp.imprimante,
            imp.get_statut_display(),
            imp.adresse_ip or 'N/A',
            imp.message_erreur,
        ])
    
    return response
