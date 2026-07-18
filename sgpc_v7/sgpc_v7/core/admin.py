from django.contrib import admin
from .models import (
    AutoEcole, Examinateur, ProfilAgent, Candidat, ExamenCode,
    ExamenConduite, JournalAudit, CategoriePermis, ParametreImpression
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
