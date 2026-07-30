from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            profil = getattr(request.user, 'profil', None)
            if profil and profil.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "Accès non autorisé.")
            return redirect('tableau_de_bord')
        return wrapper
    return decorator
