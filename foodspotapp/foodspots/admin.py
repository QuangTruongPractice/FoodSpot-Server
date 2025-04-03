# File: foodspots/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from foodspots.models import (
    User, Address, Tag, Restaurant, Follow, Order, OrderDetail, Payment,
    FoodCategory, Food, Menu, RestaurantReview, FoodReview, Cart, SubCart, SubCartItem
)

# Đăng ký và tùy chỉnh model User
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_staff']
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'fullname', 'username')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('fullname', 'username', 'phone_number', 'avatar')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'role', 'is_restaurant_user')}),
        ('Addresses', {'fields': ('addresses',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'fullname', 'username', 'role'),
        }),
    )
    filter_horizontal = ('addresses',)

admin.site.register(User, UserAdmin)

# Đăng ký và tùy chỉnh model Address
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'latitude', 'longitude')
    search_fields = ('name',)
    list_filter = ('latitude', 'longitude')

# Đăng ký và tùy chỉnh model Tag
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

# Đăng ký và tùy chỉnh model Restaurant
@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone_number', 'owner', 'star_rating')
    list_filter = ('star_rating',)
    search_fields = ('name', 'phone_number', 'owner__email')
    filter_horizontal = ('tags',)

# Đăng ký và tùy chỉnh model Follow
@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'restaurant', 'status')
    list_filter = ('status',)
    search_fields = ('user__email', 'restaurant__name')

# Đăng ký và tùy chỉnh model Order
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'restaurant', 'total', 'status')
    search_fields = ('user__email', 'restaurant__name')

# Đăng ký và tùy chỉnh model OrderDetail
@admin.register(OrderDetail)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'food', 'quantity', 'sub_total')
    search_fields = ('order__id', 'food__name')

# Đăng ký và tùy chỉnh model Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'payment_method', 'status', 'amount', 'total_payment', 'created_date')
    list_filter = ('status', 'payment_method')
    search_fields = ('order__id',)

# Đăng ký và tùy chỉnh model FoodCategory
@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

# Đăng ký và tùy chỉnh model Food
@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'time_serve', 'star_rating', 'food_category')
    list_filter = ('time_serve', 'star_rating', 'food_category')
    search_fields = ('name',)

# Đăng ký và tùy chỉnh model Menu
@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'restaurant', 'time_serve', 'is_active')
    list_filter = ('time_serve', 'is_active')
    search_fields = ('name', 'restaurant__name')
    filter_horizontal = ('foods',)

# Đăng ký và tùy chỉnh model RestaurantReview
@admin.register(RestaurantReview)
class RestaurantReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'restaurant', 'star', 'created_date')
    list_filter = ('star', 'created_date')
    search_fields = ('user__email', 'restaurant__name', 'comment')

# Đăng ký và tùy chỉnh model FoodReview
@admin.register(FoodReview)
class FoodReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_detail', 'star', 'created_date')
    list_filter = ('star', 'created_date')
    search_fields = ('user__email', 'order_detail__food__name', 'comment')

# Đăng ký và tùy chỉnh model Cart
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'item_number')
    search_fields = ('user__email',)

# Đăng ký và tùy chỉnh model SubCart
@admin.register(SubCart)
class SubCartAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'restaurant', 'total_price')
    search_fields = ('cart__user__email', 'restaurant__name')

# Đăng ký và tùy chỉnh model SubCartItem
@admin.register(SubCartItem)
class SubCartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'food', 'restaurant', 'sub_cart', 'quantity', 'price')
    search_fields = ('food__name', 'restaurant__name', 'sub_cart__id')