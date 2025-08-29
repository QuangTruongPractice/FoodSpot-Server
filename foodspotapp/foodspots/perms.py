from rest_framework import permissions
from .models import Order, OrderDetail

class RestaurantOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Cho phép đọc (GET) cho tất cả
        if request.method in permissions.SAFE_METHODS:
            return True
        # Chỉ chủ sở hữu nhà hàng mới được chỉnh sửa
        return obj.owner == request.user

class IsOrderOwner(permissions.BasePermission):
    message = "You do not have permission to access this order."

    def has_permission(self, request, view):
        # Cho phép nếu người dùng là CUSTOMER hoặc RESTAURANT_USER
        return request.user and request.user.is_authenticated and request.user.role in ['CUSTOMER', 'RESTAURANT_USER']

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Order):
            return obj.user == request.user or (
                    request.user.role == 'RESTAURANT_USER' and obj.restaurant.owner == request.user
            )
        elif isinstance(obj, OrderDetail):
            return obj.order.user == request.user or (
                    request.user.role == 'RESTAURANT_USER' and obj.order.restaurant.owner == request.user
            )
        return False

class IsRestaurantOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Kiểm tra xem người dùng có phải chủ nhà hàng của Food không
        if hasattr(obj, 'menus') and obj.menus.exists():
            restaurant = obj.menus.first().restaurant
            return restaurant and restaurant.owner == request.user and restaurant.owner.is_approved
        return False

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

# class IsChatParticipant(permissions.BasePermission):
#     def has_object_permission(self, request, view, obj):
#         user = request.user
#         return obj.user1 == user or obj.user2 == user