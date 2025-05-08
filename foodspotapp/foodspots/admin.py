from django.contrib import admin
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from .models import (
    User, Restaurant, Food, FoodCategory, FoodPrice,
    Menu, Cart, SubCart, SubCartItem, Order, OrderDetail
)

User = get_user_model()

# Đăng ký model User
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_approved', 'is_active')
    list_filter = ('role', 'is_approved', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    actions = ['approve_users']

    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, "Đã phê duyệt các tài khoản được chọn.")
    approve_users.short_description = "Phê duyệt tài khoản được chọn"

    # Kiểm soát quyền truy cập
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

# Đăng ký model Restaurant
@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner')  # Chỉ giữ các trường chắc chắn tồn tại
    search_fields = ['name']
    actions = ['approve_restaurants']

    def approve_restaurants(self, request, queryset):
        # Giả định có trường is_approved trong Restaurant
        queryset.update(is_approved=True)

        for r in queryset:
            email = r.owner.email if r.owner else None  # Kiểm tra owner có tồn tại không
            if email:  # Chỉ gửi email nếu có email hợp lệ
                send_mail(
                    subject="Thông báo phê duyệt nhà hàng của bạn",
                    message=f"""
    Xin chào {r.owner.first_name or 'Khách hàng'},

    Nhà hàng "{r.name}" của bạn đã được xác thực thành công! 🎉
    Hãy đăng nhập bằng tài khoản và mật khẩu bạn đã đăng ký với chúng tôi.

    Cảm ơn bạn đã tham gia nền tảng của chúng tôi!

    Trân trọng,
    Đội ngũ quản trị.
    """,
                    from_email="lequoctrunggg@gmail.com",
                    recipient_list=[email],
                    fail_silently=True,  # Không gây lỗi nếu gửi email thất bại
                )

        self.message_user(request, "Nhà hàng đã được phê duyệt!")
    approve_restaurants.short_description = "Phê duyệt nhà hàng đã chọn"

    # Kiểm soát quyền truy cập
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

# Đăng ký model Food
@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant')
    search_fields = ('name',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(FoodPrice)
class FoodPriceAdmin(admin.ModelAdmin):
    list_display = ('food', 'price')  # Loại bỏ 'created_at'
    search_fields = ('food__name',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('restaurant',)
    search_fields = ('restaurant__name',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__email',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(SubCart)
class SubCartAdmin(admin.ModelAdmin):
    list_display = ('cart', 'restaurant')
    search_fields = ('cart__user__email', 'restaurant__name')

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(SubCartItem)
class SubCartItemAdmin(admin.ModelAdmin):
    list_display = ('sub_cart', 'food', 'quantity')
    search_fields = ('food__name',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'status')
    list_filter = ('status',)
    search_fields = ('user__email',)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

@admin.register(OrderDetail)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = ('order', 'food', 'quantity')
    search_fields = ('food__name', 'order__user__email')

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == 'ADMIN'