from django.http import Http404
from django.shortcuts import get_object_or_404, redirect

from .models import Recipe


def _int_from_base36(code: str) -> int:
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    normalized_code = code.lower().strip()
    number = 0

    for symbol in normalized_code:
        if symbol not in alphabet:
            raise ValueError('bad base36')
        number = number * 36 + alphabet.index(symbol)

    return number


def short_link_redirect(request, code: str):
    try:
        recipe_id = _int_from_base36(code)
    except ValueError as error:
        raise Http404 from error

    recipe = get_object_or_404(Recipe, id=recipe_id)
    return redirect(f'/recipes/{recipe.id}')
