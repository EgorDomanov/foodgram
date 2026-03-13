from django.shortcuts import get_object_or_404, redirect

from .models import Recipe


def _int_from_base36(code: str) -> int:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    code = code.lower().strip()
    num = 0
    for ch in code:
        if ch not in alphabet:
            raise ValueError("bad base36")
        num = num * 36 + alphabet.index(ch)
    return num


def short_link_redirect(request, code: str):
    recipe_id = _int_from_base36(code)
    recipe = get_object_or_404(Recipe, id=recipe_id)
    return redirect(f'/recipes/{recipe.id}')