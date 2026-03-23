from string import digits

from django.contrib.auth import get_user_model, password_validation
from djoser.serializers import (
    UserCreateSerializer as DjoserUserCreateSerializer,
)
from rest_framework import serializers

from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag
from users.models import Subscription

from .fields import Base64ImageField

User = get_user_model()
DIGIT_SET = set(digits)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = '__all__'


class UserCreateSerializer(DjoserUserCreateSerializer):
    class Meta(DjoserUserCreateSerializer.Meta):
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'password',
        )


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )

    def get_is_subscribed(self, author):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return request.user.subscriptions.filter(
            author_id=author.pk,
        ).exists()


class SetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField()
    current_password = serializers.CharField()

    def validate(self, attrs):
        request = self.context.get('request')
        if request is None:
            raise serializers.ValidationError('Некорректный запрос.')

        user = request.user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError(
                {'current_password': ('Неверный пароль.',)}
            )

        password_validation.validate_password(
            attrs['new_password'],
            user=user,
        )
        return attrs


class SetAvatarSerializer(serializers.Serializer):
    avatar = Base64ImageField()


class SetAvatarResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('avatar',)


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id', read_only=True)
    name = serializers.CharField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        read_only=True,
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True,
    )
    is_favorited = serializers.BooleanField(read_only=True)
    is_in_shopping_cart = serializers.BooleanField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )


class IngredientAmountWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ('user', 'author')

    def validate(self, attrs):
        user = attrs['user']
        author = attrs['author']

        if user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя.'
            )

        if user.subscriptions.filter(author_id=author.pk).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя.'
            )

        return attrs


class SubscriptionDeleteSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
    )
    author = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
    )

    def validate(self, attrs):
        user = attrs['user']
        author = attrs['author']

        if not user.subscriptions.filter(author_id=author.pk).exists():
            raise serializers.ValidationError(
                'Вы не подписаны на этого пользователя.'
            )

        return attrs


class BaseRecipeRelationSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
    )
    recipe = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(),
    )


class RecipeRelationCreateSerializer(BaseRecipeRelationSerializer):
    def validate(self, attrs):
        relation_model = self.context.get('model_class')
        if relation_model is None:
            raise serializers.ValidationError(
                'Некорректный тип связи.'
            )

        user = attrs['user']
        recipe = attrs['recipe']

        if relation_model.objects.filter(
            user_id=user.pk,
            recipe_id=recipe.pk,
        ).exists():
            raise serializers.ValidationError(
                'Связь уже существует.'
            )

        return attrs

    def create(self, validated_data):
        relation_model = self.context['model_class']
        return relation_model.objects.create(**validated_data)


class RecipeRelationDeleteSerializer(BaseRecipeRelationSerializer):
    def validate(self, attrs):
        relation_model = self.context.get('model_class')
        if relation_model is None:
            raise serializers.ValidationError(
                'Некорректный тип связи.'
            )

        user = attrs['user']
        recipe = attrs['recipe']

        if not relation_model.objects.filter(
            user_id=user.pk,
            recipe_id=recipe.pk,
        ).exists():
            raise serializers.ValidationError(
                'Связь для удаления не найдена.'
            )

        return attrs


class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients = IngredientAmountWriteSerializer(many=True)
    tags = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'ingredients',
            'tags',
            'image',
            'name',
            'text',
            'cooking_time',
        )

    def validate(self, attrs):
        ingredients = attrs.get('ingredients', ())
        if not ingredients:
            raise serializers.ValidationError(
                {'ingredients': ['Это поле обязательно.']}
            )

        ingredient_ids = tuple(
            ingredient_item['id']
            for ingredient_item in ingredients
        )
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {'ingredients': ['Ингредиенты не должны повторяться.']}
            )

        tag_ids = tuple(attrs.get('tags', ()))
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError(
                {'tags': ['Теги не должны повторяться.']}
            )

        return attrs

    def _set_tags_and_ingredients(
        self,
        recipe,
        tags_ids,
        ingredients_data,
    ):
        recipe.tags.set(Tag.objects.filter(id__in=tags_ids))
        recipe.recipe_ingredients.all().delete()

        ingredient_ids = tuple(
            ingredient_item['id']
            for ingredient_item in ingredients_data
        )
        ingredient_map = {
            ingredient.pk: ingredient
            for ingredient in Ingredient.objects.filter(
                id__in=ingredient_ids
            )
        }

        recipe_ingredients = []
        for ingredient_item in ingredients_data:
            ingredient_id = ingredient_item['id']
            ingredient = ingredient_map.get(ingredient_id)
            if ingredient is None:
                raise serializers.ValidationError(
                    {'ingredients': ['Некорректный id ингредиента.']}
                )

            recipe_ingredients.append(
                RecipeIngredient(
                    recipe=recipe,
                    ingredient=ingredient,
                    amount=ingredient_item['amount'],
                )
            )

        RecipeIngredient.objects.bulk_create(recipe_ingredients)

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags_ids = validated_data.pop('tags')
        validated_data['author'] = self.context['request'].user

        recipe = super().create(validated_data)
        self._set_tags_and_ingredients(recipe, tags_ids, ingredients)
        return recipe

    def update(self, instance, validated_data):
        ingredients = validated_data.pop('ingredients', None)
        tags_ids = validated_data.pop('tags', None)

        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()

        if tags_ids is not None and ingredients is not None:
            self._set_tags_and_ingredients(
                instance,
                tags_ids,
                ingredients,
            )
            return instance

        if tags_ids is not None:
            instance.tags.set(Tag.objects.filter(id__in=tags_ids))

        if ingredients is not None:
            current_tag_ids = tuple(
                instance.tags.values_list('id', flat=True)
            )
            self._set_tags_and_ingredients(
                instance,
                current_tag_ids,
                ingredients,
            )

        return instance


class RecipeUpdateSerializer(RecipeCreateSerializer):
    image = Base64ImageField(required=False)


class UserWithRecipesSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count',
        read_only=True,
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'recipes',
            'recipes_count',
        )

    def get_recipes(self, author):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        recipes = author.recipes.order_by('-created_at')

        if limit and set(limit) <= DIGIT_SET:
            recipes = recipes[:int(limit)]

        return RecipeMinifiedSerializer(
            recipes,
            many=True,
            context=self.context,
        ).data
