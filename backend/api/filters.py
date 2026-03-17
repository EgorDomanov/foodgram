import django_filters as filters
from recipes.models import Recipe, Tag


class RecipeFilter(filters.FilterSet):
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )
    author = filters.NumberFilter(field_name='author__id')

    is_favorited = filters.NumberFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.NumberFilter(
        method='filter_is_in_shopping_cart',
    )

    class Meta:
        model = Recipe
        fields = ('tags', 'author')

    def filter_is_favorited(self, queryset, name, value):
        user = getattr(self.request, 'user', None)
        if value != 1:
            return queryset
        if not user or user.is_anonymous:
            return queryset.none()
        return queryset.filter(favorited_by__user=user)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        user = getattr(self.request, 'user', None)
        if value != 1:
            return queryset
        if not user or user.is_anonymous:
            return queryset.none()
        return queryset.filter(in_shopping_carts__user=user)
