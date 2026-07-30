from django.contrib import admin
from .models import (
    AutoEcole, Examinateur, ProfilAgent, Candidat, ExamenCode,
    ExamenConduite, JournalAudit, CategoriePermis, ParametreImpression,
    JournalImpression
)
admin.site.register(AutoEcole)
admin.site.register(Examinateur)
admin.site.register(ProfilAgent)
admin.site.register(Candidat)
admin.site.register(ExamenCode)
admin.site.register(ExamenConduite)
admin.site.register(JournalAudit)
admin.site.register(CategoriePermis)
admin.site.register(ParametreImpression)

@admin.register(JournalImpression)
class JournalImpressionAdmin(admin.ModelAdmin):
    list_display = ('date_impression', 'agent', 'type_fiche', 'candidat', 'adresse_ip')
    list_filter = ('type_fiche', 'date_impression')
    search_fields = ('candidat__nom', 'agent__user__username')
    readonly_fields = ('date_impression', 'adresse_ip')