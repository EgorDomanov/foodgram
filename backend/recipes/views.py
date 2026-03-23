from django.http import Http404
from django.shortcuts import get_object_or_404, redirect

from .base36 import decode_base36
from .models import Recipe


def short_link_redirect(request, code: str):
    try:
        recipe_id = decode_base36(code)
    except ValueError as error:
        raise Http404 from error

    recipe = get_object_or_404(Recipe, id=recipe_id)
    return redirect(f'/recipes/{recipe.id}')
