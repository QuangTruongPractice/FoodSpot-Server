from rest_framework import permissions

class RestaurantOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Cho phép đọc (GET) cho tất cả
        if request.method in permissions.SAFE_METHODS:
            return True
        # Chỉ chủ sở hữu nhà hàng mới được chỉnh sửa
        return obj.owner == request.user