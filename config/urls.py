from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', views.connexion, name='connexion'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),

    # Candidats
    path('candidats/', views.liste_candidats, name='liste_candidats'),
    path('candidats/nouveau/', views.creer_candidat, name='creer_candidat'),
    path('candidats/ancien-dossier/', views.saisir_ancien_dossier, name='saisir_ancien_dossier'),
    path('candidats/<int:pk>/', views.detail_candidat, name='detail_candidat'),
    path('candidats/<int:pk>/modifier/', views.modifier_candidat, name='modifier_candidat'),
    path('candidats/<int:pk>/programmer-code/', views.programmer_code, name='programmer_code'),
    path('candidats/<int:pk>/reprogrammer-code/', views.reprogrammer_code, name='reprogrammer_code'),
    path('candidats/<int:pk>/programmer-conduite/', views.programmer_conduite, name='programmer_conduite'),
    path('candidats/examen-code/<int:pk>/modifier-date/', views.modifier_date_examen_code, name='modifier_date_examen_code'),
    path('candidats/examen-conduite/<int:pk>/modifier-date/', views.modifier_date_examen_conduite, name='modifier_date_examen_conduite'),

    # Fiches impression
    path('candidats/<int:pk>/fiche-controle/', views.imprimer_fiche_controle, name='imprimer_fiche_controle'),
    path('fiches/examen-code/', views.fiche_examen_code, name='fiche_examen_code'),
    path('fiches/examen-conduite/', views.fiche_examen_conduite, name='fiche_examen_conduite'),

    # Examens
    path('examens/code/', views.examens_code_jour, name='examens_code_jour'),
    path('examens/conduite/', views.examens_conduite_jour, name='examens_conduite_jour'),
    path('examens/code/<int:pk>/saisir/', views.saisir_resultat_code, name='saisir_resultat_code'),
    path('examens/conduite/<int:pk>/saisir/', views.saisir_resultat_conduite, name='saisir_resultat_conduite'),
    path('examens/<str:type_examen>/imprimer/', views.imprimer_liste_examens, name='imprimer_liste_examens'),

    # Absents / reprogrammation
    path('absents/', views.liste_absents, name='liste_absents'),
    path('absents/<int:pk>/<str:type_examen>/programmer/', views.programmer_absent, name='programmer_absent'),

    # Attestations
    path('attestations/', views.liste_attestations, name='liste_attestations'),
    path('attestations/<int:pk>/imprimer/', views.imprimer_attestation, name='imprimer_attestation'),
    path('verification/<int:pk>/', views.verification_attestation, name='verification_attestation'),

    # Rapports
    path('rapports/', views.rapports, name='rapports'),

    # Admin
    path('admin-sgpc/agents/', views.liste_agents, name='liste_agents'),
    path('admin-sgpc/agents/nouveau/', views.creer_agent, name='creer_agent'),
    path('admin-sgpc/agents/<int:pk>/toggle/', views.toggle_agent, name='toggle_agent'),
    path('admin-sgpc/auto-ecoles/', views.liste_auto_ecoles, name='liste_auto_ecoles'),
    path('admin-sgpc/auto-ecoles/nouvelle/', views.creer_auto_ecole, name='creer_auto_ecole'),
    path('admin-sgpc/auto-ecoles/<int:pk>/modifier/', views.modifier_auto_ecole, name='modifier_auto_ecole'),
    path('admin-sgpc/examinateurs/', views.liste_examinateurs, name='liste_examinateurs'),
    path('admin-sgpc/examinateurs/nouveau/', views.creer_examinateur, name='creer_examinateur'),
    path('admin-sgpc/examinateurs/<int:pk>/toggle/', views.toggle_examinateur, name='toggle_examinateur'),
    path('admin-sgpc/categories/', views.liste_categories, name='liste_categories'),
    path('admin-sgpc/categories/nouvelle/', views.creer_categorie, name='creer_categorie'),
    path('admin-sgpc/categories/<int:pk>/toggle/', views.toggle_categorie, name='toggle_categorie'),
    path('admin-sgpc/audit/', views.journal_audit, name='journal_audit'),
    path('admin-sgpc/parametres/', views.parametres_impression, name='parametres_impression'),
    path('admin-sgpc/parametres/<str:type_fiche>/editeur/', views.editeur_position, name='editeur_position'),
    path('admin-sgpc/parametres/<str:type_fiche>/sauvegarder/', views.sauvegarder_positions, name='sauvegarder_positions'),
    path('admin-sgpc/parametres/champ/<int:pk>/modifier/', views.modifier_champ_position, name='modifier_champ_position'),
    path('admin-sgpc/parametres/<str:type_fiche>/test/', views.test_impression, name='test_impression'),
    path('admin-sgpc/rapports/', views.rapports_admin, name='rapports_admin'),

    # API
    path('api/auto-ecoles/autocomplete/', views.autocomplete_auto_ecole, name='autocomplete_auto_ecole'),

    # Portail candidat (public)
    path('candidat/connexion/', views.candidat_connexion, name='candidat_connexion'),
    path('candidat/deconnexion/', views.candidat_deconnexion, name='candidat_deconnexion'),
    path('candidat/resultats/', views.candidat_resultats, name='candidat_resultats'),
]
