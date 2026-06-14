from django.contrib import admin
from .models import AutoEcole, ProfilAgent, Candidat, ExamenCode, ExamenConduite, JournalAudit

admin.site.register(AutoEcole)
admin.site.register(ProfilAgent)
admin.site.register(Candidat)
admin.site.register(ExamenCode)
admin.site.register(ExamenConduite)
admin.site.register(JournalAudit)
