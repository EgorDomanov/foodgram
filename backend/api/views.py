from django.db.models import Sum
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from users.models import Subscription, User

from .filters import RecipeFilter
from .pagination import CustomPagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    IngredientSerializer,
    RecipeCreateSerializer,
    RecipeMinifiedSerializer,
    RecipeReadSerializer,
    RecipeUpdateSerializer,
    SetAvatarResponseSerializer,
    SetAvatarSerializer,
    SetPasswordSerializer,
    TagSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserWithRecipesSerializer,
)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    pagination_class = None

    def get_queryset(self):
        qs = Ingredient.objects.all()
        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__istartswith=name)
        return qs


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('subscriptions', 'subscribe'):
            return UserWithRecipesSerializer
        if self.action == 'set_password':
            return SetPasswordSerializer
        if self.action == 'avatar':
            return SetAvatarSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in (
            'me',
            'set_password',
            'subscriptions',
            'subscribe',
            'avatar',
        ):
            return (IsAuthenticated(),)
        return (AllowAny(),)

    @action(methods=('get',), detail=False, url_path='me')
    def me(self, request):
        serializer = UserSerializer(
            request.user,
            context={'request': request},
        )
        return Response(serializer.data)

    @action(methods=('post',), detail=False, url_path='set_password')
    def set_password(self, request):
        serializer = SetPasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(
            serializer.validated_data['new_password']
        )
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=('get',), detail=False, url_path='subscriptions')
    def subscriptions(self, request):
        authors = User.objects.filter(
            subscribers__user=request.user
        ).distinct()
        page = self.paginate_queryset(authors)
        serializer = UserWithRecipesSerializer(
            page,
            many=True,
            context={'request': request},
        )
        return self.get_paginated_response(serializer.data)

    @action(methods=('post', 'delete'), detail=True, url_path='subscribe')
    def subscribe(self, request, pk=None):
        author = self.get_object()

        if request.method == 'POST':
            if author == request.user:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            if Subscription.objects.filter(
                user=request.user,
                author=author,
            ).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST)
            Subscription.objects.create(
                user=request.user,
                author=author,
            )
            serializer = UserWithRecipesSerializer(
                author,
                context={'request': request},
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        sub = Subscription.objects.filter(
            user=request.user,
            author=author,
        )
        if not sub.exists():
            return Response(status=status.HTTP_400_BAD_REQUEST)
        sub.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=('put', 'delete'), detail=False, url_path='me/avatar')
    def avatar(self, request):
        if request.method == 'PUT':
            serializer = SetAvatarSerializer(
                data=request.data,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            request.user.avatar = serializer.validated_data['avatar']
            request.user.save()
            resp = SetAvatarResponseSerializer(
                request.user,
                context={'request': request},
            )
            return Response(resp.data, status=status.HTTP_200_OK)

        request.user.avatar = None
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _base36(num: int) -> str:
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    if num == 0:
        return '0'
    s = ''
    while num > 0:
        num, r = divmod(num, 36)
        s = alphabet[r] + s
    return s


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().select_related(
        'author'
    ).prefetch_related(
        'tags',
        'recipe_ingredients__ingredient',
    )
    filterset_class = RecipeFilter
    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeReadSerializer
        if self.action == 'create':
            return RecipeCreateSerializer
        if self.action in ('partial_update', 'update'):
            return RecipeUpdateSerializer
        return RecipeUpdateSerializer

    def get_permissions(self):
        if self.action in (
            'create',
            'update',
            'partial_update',
            'destroy',
            'favorite',
            'shopping_cart',
            'download_shopping_cart',
        ):
            if self.action in (
                'create',
                'favorite',
                'shopping_cart',
                'download_shopping_cart',
            ):
                return (IsAuthenticated(),)
            return (IsAuthenticated(), IsAuthorOrReadOnly())
        return (AllowAny(),)

    def create(self, request, *args, **kwargs):
        serializer = RecipeCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out = RecipeReadSerializer(
            recipe,
            context={'request': request},
        )
        return Response(out.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        recipe = self.get_object()
        serializer = RecipeUpdateSerializer(
            recipe,
            data=request.data,
            partial=False,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out = RecipeReadSerializer(
            recipe,
            context={'request': request},
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(
        methods=('get',),
        detail=False,
        url_path='download_shopping_cart',
        permission_classes=(IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        ingredients = (
            RecipeIngredient.objects
            .filter(recipe__in_shopping_carts__user=request.user)
            .values(
                'ingredient__name',
                'ingredient__measurement_unit',
            )
            .annotate(total=Sum('amount'))
            .order_by('ingredient__name')
        )

        lines = []
        for item in ingredients:
            name = item['ingredient__name']
            unit = item['ingredient__measurement_unit']
            total = item['total']
            lines.append(f'{name} ({unit}) — {total}')

        content = '\n'.join(lines) if lines else 'Список покупок пуст.'
        response = HttpResponse(
            content,
            content_type='text/plain; charset=utf-8',
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    @action(
        methods=('get',),
        detail=True,
        url_path='get-link',
        permission_classes=(AllowAny,),
    )
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        code = _base36(recipe.id)
        short_link = request.build_absolute_uri(f'/s/{code}')
        return Response(
            {'short-link': short_link},
            status=status.HTTP_200_OK,
        )

    def _add_del_relation(
        self,
        request,
        model_cls,
        serializer_cls,
        pk,
        err_on_add=True,
    ):
        recipe = self.get_object()

        if request.method == 'POST':
            if model_cls.objects.filter(
                user=request.user,
                recipe=recipe,
            ).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST)
            model_cls.objects.create(
                user=request.user,
                recipe=recipe,
            )
            ser = serializer_cls(
                recipe,
                context={'request': request},
            )
            return Response(
                ser.data,
                status=status.HTTP_201_CREATED,
            )

        obj = model_cls.objects.filter(
            user=request.user,
            recipe=recipe,
        )
        if not obj.exists():
            return Response(status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=('post', 'delete'),
        detail=True,
        url_path='favorite',
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        return self._add_del_relation(
            request,
            Favorite,
            RecipeMinifiedSerializer,
            pk,
        )

    @action(
        methods=('post', 'delete'),
        detail=True,
        url_path='shopping_cart',
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        return self._add_del_relation(
            request,
            ShoppingCart,
            RecipeMinifiedSerializer,
            pk,
        )
