from rest_framework import permissions
from .models import Order

class RestaurantOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Cho phép đọc (GET) cho tất cả
        if request.method in permissions.SAFE_METHODS:
            return True
        # Chỉ chủ sở hữu nhà hàng mới được chỉnh sửa
        return obj.owner == request.user

class IsOrderOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Order):
            return obj.user == request.user or (
                    request.user.role == 'RESTAURANT_USER' and obj.restaurant.owner == request.user
            )
        return False

class IsRestaurantOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Kiểm tra nếu người dùng là chủ nhà hàng của món ăn (food)
        return obj.restaurant.user == request.user  # `restaurant.user` là chủ nhà hàng

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        # Kiểm tra nếu người dùng đã đăng nhập và có role là 'ADMIN'
        return request.user.is_authenticated and request.user.role == 'ADMIN'

    def has_object_permission(self, request, view, obj):
        # Đối với quyền truy cập đối tượng, kiểm tra role của người dùng
        return request.user.role == 'ADMIN'

class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Chỉ cho phép người dùng sở hữu đánh giá hoặc admin thao tác
        return obj.user == request.user or request.user.role == 'ADMIN'

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user