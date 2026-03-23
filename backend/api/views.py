import io

from django.contrib.auth import get_user_model
from django.db.models import (
    Case,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Sum,
    Value,
    When,
)
from django.http import FileResponse
from django.urls import reverse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from recipes.base36 import encode_base36
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)

from .filters import RecipeFilter
from .pagination import LimitPagination
from .permissions import IsAuthenticatedAuthorOrReadOnly
from .serializers import (
    IngredientSerializer,
    RecipeCreateSerializer,
    RecipeMinifiedSerializer,
    RecipeReadSerializer,
    RecipeRelationCreateSerializer,
    RecipeRelationDeleteSerializer,
    RecipeUpdateSerializer,
    SetAvatarResponseSerializer,
    SetAvatarSerializer,
    SetPasswordSerializer,
    SubscriptionCreateSerializer,
    SubscriptionDeleteSerializer,
    TagSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserWithRecipesSerializer,
)

User = get_user_model()


class RelationActionMixin:
    def _get_validation_serializer(
        self,
        serializer_class,
        serializer_data,
        **extra_context,
    ):
        serializer_context = self.get_serializer_context()
        serializer_context.update(extra_context)

        serializer = serializer_class(
            data=serializer_data,
            context=serializer_context,
        )
        serializer.is_valid(raise_exception=True)
        return serializer

    def _create_relation(
        self,
        serializer_class,
        serializer_data,
        response_serializer_class,
        response_instance,
        **extra_context,
    ):
        serializer = self._get_validation_serializer(
            serializer_class=serializer_class,
            serializer_data=serializer_data,
            **extra_context,
        )
        serializer.save()

        response_serializer = response_serializer_class(
            response_instance,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def _delete_relation(
        self,
        serializer_class,
        serializer_data,
        queryset_getter,
        **extra_context,
    ):
        serializer = self._get_validation_serializer(
            serializer_class=serializer_class,
            serializer_data=serializer_data,
            **extra_context,
        )
        queryset_getter(serializer.validated_data).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BaseReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = None


class TagViewSet(BaseReadOnlyViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(BaseReadOnlyViewSet):
    serializer_class = IngredientSerializer

    def get_queryset(self):
        queryset = Ingredient.objects.all()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class UserViewSet(
    RelationActionMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    pagination_class = LimitPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in {'subscriptions', 'subscribe'}:
            return UserWithRecipesSerializer
        if self.action == 'set_password':
            return SetPasswordSerializer
        if self.action == 'avatar':
            return SetAvatarSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in {
            'me',
            'set_password',
            'subscriptions',
            'subscribe',
            'avatar',
        }:
            return (IsAuthenticated(),)
        return (AllowAny(),)

    @action(detail=False, url_path='me')
    def me(self, request):
        serializer = UserSerializer(
            request.user,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(methods=('post',), detail=False, url_path='set_password')
    def set_password(self, request):
        serializer = SetPasswordSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(
            serializer.validated_data['new_password']
        )
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, url_path='subscriptions')
    def subscriptions(self, request):
        author_ids = request.user.subscriptions.values_list(
            'author_id',
            flat=True,
        )
        authors = User.objects.filter(id__in=author_ids).distinct()
        page = self.paginate_queryset(authors)
        serializer = UserWithRecipesSerializer(
            page,
            many=True,
            context=self.get_serializer_context(),
        )
        return self.get_paginated_response(serializer.data)

    @action(methods=('post', 'delete'), detail=True, url_path='subscribe')
    def subscribe(self, request, pk=None):
        author = self.get_object()
        serializer_data = {
            'user': request.user.pk,
            'author': author.pk,
        }

        if request.method == 'POST':
            return self._create_relation(
                serializer_class=SubscriptionCreateSerializer,
                serializer_data=serializer_data,
                response_serializer_class=UserWithRecipesSerializer,
                response_instance=author,
            )

        return self._delete_relation(
            serializer_class=SubscriptionDeleteSerializer,
            serializer_data=serializer_data,
            queryset_getter=lambda data: data['user'].subscriptions.filter(
                author_id=data['author'].pk,
            ),
        )

    @action(methods=('put', 'delete'), detail=False, url_path='me/avatar')
    def avatar(self, request):
        if request.method == 'PUT':
            serializer = SetAvatarSerializer(
                data=request.data,
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            request.user.avatar = serializer.validated_data['avatar']
            request.user.save()

            response_serializer = SetAvatarResponseSerializer(
                request.user,
                context=self.get_serializer_context(),
            )
            return Response(response_serializer.data)

        request.user.avatar = None
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeViewSet(RelationActionMixin, viewsets.ModelViewSet):
    filterset_class = RecipeFilter
    permission_classes = (IsAuthenticatedAuthorOrReadOnly,)
    pagination_class = LimitPagination

    def get_queryset(self):
        queryset = Recipe.objects.select_related(
            'author',
        ).prefetch_related(
            'tags',
            'recipe_ingredients__ingredient',
        )

        user = self.request.user
        if not user.is_authenticated:
            return queryset.annotate(
                is_favorited=Value(0, output_field=IntegerField()),
                is_in_shopping_cart=Value(
                    0,
                    output_field=IntegerField(),
                ),
            )

        favorite_subquery = Favorite.objects.filter(
            user_id=user.pk,
            recipe_id=OuterRef('pk'),
        )
        shopping_cart_subquery = ShoppingCart.objects.filter(
            user_id=user.pk,
            recipe_id=OuterRef('pk'),
        )
        return queryset.annotate(
            is_favorited=Case(
                When(
                    Exists(favorite_subquery),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
            is_in_shopping_cart=Case(
                When(
                    Exists(shopping_cart_subquery),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )

    def get_serializer_class(self):
        if self.action in {'list', 'retrieve'}:
            return RecipeReadSerializer
        if self.action == 'create':
            return RecipeCreateSerializer
        return RecipeUpdateSerializer

    def get_permissions(self):
        if self.action in {
            'create',
            'favorite',
            'shopping_cart',
            'download_shopping_cart',
        }:
            return (IsAuthenticated(),)
        if self.action in {'update', 'partial_update', 'destroy'}:
            return (IsAuthenticatedAuthorOrReadOnly(),)
        return (AllowAny(),)

    def create(self, request, *args, **kwargs):
        serializer = RecipeCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()

        response_serializer = RecipeReadSerializer(
            recipe,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._save_recipe(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._save_recipe(request, partial=True)

    def _save_recipe(self, request, partial):
        recipe = self.get_object()
        serializer = RecipeUpdateSerializer(
            recipe,
            data=request.data,
            partial=partial,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()

        response_serializer = RecipeReadSerializer(
            recipe,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data)

    @action(
        detail=False,
        url_path='download_shopping_cart',
        permission_classes=(IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        ingredients = (
            RecipeIngredient.objects.filter(
                recipe__in_shopping_carts__user_id=request.user.pk,
            )
            .values(
                name=F('ingredient__name'),
                unit=F('ingredient__measurement_unit'),
            )
            .annotate(total=Sum('amount'))
            .order_by('name')
        )

        content = '\n'.join(
            f'{ingredient_data["name"]} '
            f'({ingredient_data["unit"]}) — '
            f'{ingredient_data["total"]}'
            for ingredient_data in ingredients
        )
        if not content:
            content = 'Список покупок пуст.'

        shopping_list = io.BytesIO(content.encode('utf-8'))
        return FileResponse(
            shopping_list,
            as_attachment=True,
            filename='shopping_list.txt',
            content_type='text/plain; charset=utf-8',
        )

    @action(
        detail=True,
        url_path='get-link',
        permission_classes=(AllowAny,),
    )
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        code = encode_base36(recipe.pk)
        short_path = reverse('short-link', args=(code,))
        short_link = request.build_absolute_uri(short_path)
        return Response({'short-link': short_link})

    def _recipe_relation_data(self, request, recipe):
        return {
            'user': request.user.pk,
            'recipe': recipe.pk,
        }

    def _create_recipe_relation(self, request, relation_model):
        recipe = self.get_object()
        serializer_data = self._recipe_relation_data(request, recipe)
        return self._create_relation(
            serializer_class=RecipeRelationCreateSerializer,
            serializer_data=serializer_data,
            response_serializer_class=RecipeMinifiedSerializer,
            response_instance=recipe,
            model_class=relation_model,
        )

    def _delete_recipe_relation(self, request, relation_model):
        recipe = self.get_object()
        serializer_data = self._recipe_relation_data(request, recipe)
        return self._delete_relation(
            serializer_class=RecipeRelationDeleteSerializer,
            serializer_data=serializer_data,
            queryset_getter=lambda data: relation_model.objects.filter(
                user_id=data['user'].pk,
                recipe_id=data['recipe'].pk,
            ),
            model_class=relation_model,
        )

    @action(
        methods=('post', 'delete'),
        detail=True,
        url_path='favorite',
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        if request.method == 'POST':
            return self._create_recipe_relation(request, Favorite)
        return self._delete_recipe_relation(request, Favorite)

    @action(
        methods=('post', 'delete'),
        detail=True,
        url_path='shopping_cart',
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self._create_recipe_relation(
                request,
                ShoppingCart,
            )
        return self._delete_recipe_relation(
            request,
            ShoppingCart,
        )
