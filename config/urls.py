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
    path('candidats/<int:pk>/', views.detail_candidat, name='detail_candidat'),
    path('candidats/<int:pk>/reprogrammer/<str:type_examen>/',
         views.reprogrammer_candidat, name='reprogrammer_candidat'),

    # Examens
    path('examens/code/', views.examens_code_jour, name='examens_code_jour'),
    path('examens/conduite/', views.examens_conduite_jour, name='examens_conduite_jour'),
    path('examens/<str:type_examen>/imprimer/', views.imprimer_liste_examens, name='imprimer_liste_examens'),

    # Absents
    path('absents/', views.liste_absents, name='liste_absents'),
    path('absents/<int:pk>/<str:type_examen>/programmer/', views.programmer_absent, name='programmer_absent'),
    path('examens/code/<int:pk>/saisir/', views.saisir_resultat_code, name='saisir_resultat_code'),
    path('examens/conduite/<int:pk>/saisir/', views.saisir_resultat_conduite, name='saisir_resultat_conduite'),

    # Attestations
    path('attestations/', views.liste_attestations, name='liste_attestations'),
    path('attestations/<int:pk>/imprimer/', views.imprimer_attestation, name='imprimer_attestation'),

    # Rapports
    path('rapports/', views.rapports, name='rapports'),

    # Admin : Agents
    path('admin-sgpc/agents/', views.liste_agents, name='liste_agents'),
    path('admin-sgpc/agents/nouveau/', views.creer_agent, name='creer_agent'),
    path('admin-sgpc/agents/<int:pk>/toggle/', views.toggle_agent, name='toggle_agent'),

    # Admin : Auto-écoles
    path('admin-sgpc/auto-ecoles/', views.liste_auto_ecoles, name='liste_auto_ecoles'),
    path('admin-sgpc/auto-ecoles/nouvelle/', views.creer_auto_ecole, name='creer_auto_ecole'),
    path('admin-sgpc/auto-ecoles/<int:pk>/modifier/', views.modifier_auto_ecole, name='modifier_auto_ecole'),

    # Admin : Audit
    path('admin-sgpc/audit/', views.journal_audit, name='journal_audit'),

    # API
    path('api/auto-ecoles/autocomplete/', views.autocomplete_auto_ecole, name='autocomplete_auto_ecole'),
]
