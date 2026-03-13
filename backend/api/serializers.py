from django.contrib.auth import password_validation
from djoser.serializers import UserCreateSerializer as DjoserUserCreateSerializer
from rest_framework import serializers

from recipes.models import (
    Tag, Ingredient, Recipe, RecipeIngredient, Favorite, ShoppingCart
)
from users.models import User, Subscription
from .fields import Base64ImageField



class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')



class UserCreateSerializer(DjoserUserCreateSerializer):
    class Meta(DjoserUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'password')


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'is_subscribed', 'avatar'
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(user=request.user, author=obj).exists()


class SetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField()
    current_password = serializers.CharField()

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': ['Неверный пароль.']})
        password_validation.validate_password(attrs['new_password'], user=user)
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
    amount = serializers.IntegerField()

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit', 'amount')



class RecipeReadSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time'
        )

    def get_ingredients(self, obj):
        qs = obj.recipe_ingredients.select_related('ingredient')
        return [
            {
                'id': item.ingredient.id,
                'name': item.ingredient.name,
                'measurement_unit': item.ingredient.measurement_unit,
                'amount': item.amount
            }
            for item in qs
        ]

    def _bool_for_user(self, model_cls, obj):
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return model_cls.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_favorited(self, obj):
        return self._bool_for_user(Favorite, obj)

    def get_is_in_shopping_cart(self, obj):
        return self._bool_for_user(ShoppingCart, obj)



class IngredientAmountWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients = IngredientAmountWriteSerializer(many=True)
    tags = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    image = Base64ImageField(required=True)

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image', 'name', 'text', 'cooking_time')

    def validate(self, attrs):
        ingredients = attrs.get('ingredients', [])
        if not ingredients:
            raise serializers.ValidationError({'ingredients': ['Это поле обязательно.']})

        ids = [i['id'] for i in ingredients]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({'ingredients': ['Ингредиенты не должны повторяться.']})

        tags = attrs.get('tags', [])
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError({'tags': ['Теги не должны повторяться.']})

        return attrs

    def _set_tags_and_ingredients(self, recipe, tags_ids, ingredients_data):
        recipe.tags.set(Tag.objects.filter(id__in=tags_ids))

        RecipeIngredient.objects.filter(recipe=recipe).delete()

        ingredient_map = {
            ing.id: ing for ing in Ingredient.objects.filter(id__in=[i['id'] for i in ingredients_data])
        }
        objs = []
        for item in ingredients_data:
            ing = ingredient_map.get(item['id'])
            if not ing:
                raise serializers.ValidationError({'ingredients': ['Некорректный id ингредиента.']})
            objs.append(RecipeIngredient(recipe=recipe, ingredient=ing, amount=item['amount']))

        RecipeIngredient.objects.bulk_create(objs)

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags_ids = validated_data.pop('tags')
        request = self.context['request']

        recipe = Recipe.objects.create(author=request.user, **validated_data)
        self._set_tags_and_ingredients(recipe, tags_ids, ingredients)
        return recipe


class RecipeUpdateSerializer(RecipeCreateSerializer):
    image = Base64ImageField(required=False)



class UserWithRecipesSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(source='recipes.count', read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        qs = obj.recipes.order_by('-created_at')
        if limit is not None and str(limit).isdigit():
            qs = qs[: int(limit)]
        return RecipeMinifiedSerializer(qs, many=True, context=self.context).data