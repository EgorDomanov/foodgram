from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthenticatedAuthorOrReadOnly(BasePermission):

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated

    def has_object_permission(self, request, view, instance):
        if request.method in SAFE_METHODS:
            return True
        return instance.author == request.user
