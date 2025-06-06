from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.mail import send_mail
from .models import (
    User, Address, Tag, Restaurant, Follow, Favorite, Order, OrderDetail,
    Payment, FoodCategory, Food, FoodPrice, Menu, RestaurantReview,
    FoodReview, Cart, SubCart, SubCartItem
)
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncQuarter, TruncYear
from django.utils.timezone import now
from datetime import datetime

class MyAdminSite(admin.AdminSite):
    site_header = 'FoodSpot Administration'
    index_title = 'Trang chủ'
    index_template = 'admin/custom_button.html'

    def get_urls(self):
        return [
            path('stats/', self.stats_view, name="stats")
        ] + super().get_urls()

    def stats_view(self, request):
        report_type = request.GET.get('report_type', 'month')
        successful_orders = Order.objects.filter(payments__status='SUCCESS')

        # Lấy giá trị tháng, năm, quý từ request
        month = int(request.GET.get('month', now().month))
        year = int(request.GET.get('year', now().year))
        quarter_str = request.GET.get('quarter')
        quarter = int(quarter_str) if quarter_str else None

        monthly_stats = []
        quarterly_stats = []
        yearly_stats = []

        if report_type == 'month':
            start_date = datetime(year, month, 1)
            end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

            monthly_stats = successful_orders.filter(
                ordered_date__gte=start_date,
                ordered_date__lt=end_date
            ).values('restaurant__name').annotate(
                total_revenue=Sum('total'),
                total_orders=Count('id')
            ).order_by('-total_revenue')

        elif report_type == 'quarter':
            if quarter:
                start_month = (quarter - 1) * 3 + 1
                start_date = datetime(year, start_month, 1)
                end_date = datetime(year + 1, 1, 1) if quarter == 4 else datetime(year, start_month + 3, 1)

                filtered_orders = successful_orders.filter(
                    ordered_date__gte=start_date,
                    ordered_date__lt=end_date
                )
            else:
                filtered_orders = successful_orders.filter(ordered_date__year=year)

            quarterly_stats = (
                filtered_orders
                .annotate(quarter=TruncQuarter('ordered_date'))
                .values('quarter', 'restaurant__name')
                .annotate(
                    total_revenue=Sum('total'),
                    total_orders=Count('id')
                )
                .order_by('quarter')
            )

            for item in quarterly_stats:
                dt = item['quarter']
                quarter_number = (dt.month - 1) // 3 + 1
                item['quarter_display'] = f"Q{quarter_number} - {dt.year}"

        elif report_type == 'year':
            filtered_orders = successful_orders.filter(ordered_date__year=year)

            yearly_stats = (
                filtered_orders
                .annotate(year=TruncYear('ordered_date'))
                .values('year', 'restaurant__name')
                .annotate(
                    total_revenue=Sum('total'),
                    total_orders=Count('id')
                )
                .order_by('year')
            )

        return TemplateResponse(request, 'admin/stats.html', {
            'monthly_stats': monthly_stats,
            'quarterly_stats': quarterly_stats,
            'yearly_stats': yearly_stats,
            'selected_month': month,
            'selected_year': year,
            'selected_quarter': quarter,
            'selected_type': report_type,
            'month_range': range(1, 13),
            'year_range': range(now().year - 5, now().year + 1),
            'title': 'Thống kê',
        })

class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'is_approved', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_approved', 'is_staff')
    search_fields = ('email', 'username')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username', 'first_name', 'last_name', 'phone_number', 'avatar')}),
        ('Permissions', {'fields': ('is_approved', 'is_active', 'is_staff', 'is_superuser')}),
        ('Role', {'fields': ('role',)}),
        ('Addresses', {'fields': ('addresses',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_approved'),
        }),
    )
    filter_horizontal = ('addresses',)

    def save_model(self, request, obj, form, change):
        # Lưu trạng thái ban đầu của is_approved (trước khi lưu)
        if change:  # Chỉ kiểm tra khi chỉnh sửa, không phải khi tạo mới
            original_user = User.objects.get(pk=obj.pk)
            was_approved = original_user.is_approved
        else:
            was_approved = None

        # Lưu user
        super().save_model(request, obj, form, change)

        # Gửi email nếu is_approved thay đổi từ False thành True và role là RESTAURANT_USER
        if change and was_approved is False and obj.is_approved is True and obj.role == 'RESTAURANT_USER':
            try:
                restaurant = Restaurant.objects.get(owner=obj)
                send_mail(
                    subject='Tài khoản nhà hàng của bạn đã được phê duyệt',
                    message=(
                        f'Chào {obj.email},\n\n'
                        f'Tài khoản nhà hàng "{restaurant.name}" của bạn đã được phê duyệt bởi Admin.\n'
                        'Bạn có thể bắt đầu quản lý nhà hàng và thêm món ăn trên hệ thống FoodSpots.\n\n'
                        'Trân trọng,\nĐội ngũ FoodSpots'
                    ),
                    from_email='nghianguyen.110616@gmail.com',
                    recipient_list=[obj.email],
                    fail_silently=False,
                )
                self.message_user(request, f"Email thông báo đã được gửi tới {obj.email}.")
            except Restaurant.DoesNotExist:
                self.message_user(request, f"Không tìm thấy nhà hàng liên kết với user {obj.email}. Email không được gửi.")
            except Exception as e:
                self.message_user(request, f"Lỗi khi gửi email tới {obj.email}: {str(e)}")

class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'star_rating', 'phone_number')
    list_filter = ('star_rating',)
    search_fields = ('name', 'owner__email')
    filter_horizontal = ('tags',)

class AddressAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude')
    search_fields = ('name',)

class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'restaurant', 'status')
    list_filter = ('status',)
    search_fields = ('user__email', 'restaurant__name')

class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'food', 'status')
    list_filter = ('status',)
    search_fields = ('user__email', 'food__name')

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'restaurant', 'total', 'status', 'ordered_date')
    list_filter = ('status', 'ordered_date')
    search_fields = ('user__email', 'restaurant__name')
    list_editable = ('status',)

class OrderDetailAdmin(admin.ModelAdmin):
    list_display = ('order', 'food', 'quantity', 'sub_total', 'time_serve')
    list_filter = ('time_serve',)
    search_fields = ('order__id', 'food__name')

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_method', 'status', 'total_payment', 'created_date')
    list_filter = ('status', 'created_date')
    search_fields = ('order__id',)

class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class FoodAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant', 'food_category', 'star_rating', 'is_available')
    list_filter = ('is_available', 'food_category')
    search_fields = ('name', 'restaurant__name')

class FoodPriceAdmin(admin.ModelAdmin):
    list_display = ('food', 'time_serve', 'price')
    list_filter = ('time_serve',)
    search_fields = ('food__name',)

class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant', 'time_serve', 'is_active', 'created_date')
    list_filter = ('is_active', 'time_serve')
    search_fields = ('name', 'restaurant__name')
    filter_horizontal = ('foods',)

class RestaurantReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'restaurant', 'star', 'created_date')
    list_filter = ('star', 'created_date')
    search_fields = ('user__email', 'restaurant__name')

class FoodReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'order_detail', 'star', 'created_date')
    list_filter = ('star', 'created_date')
    search_fields = ('user__email', 'order_detail__food__name')

class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_number')
    search_fields = ('user__email',)

class SubCartAdmin(admin.ModelAdmin):
    list_display = ('cart', 'restaurant', 'total_price')
    search_fields = ('cart__user__email', 'restaurant__name')

class SubCartItemAdmin(admin.ModelAdmin):
    list_display = ('sub_cart', 'food', 'quantity', 'price', 'time_serve')
    list_filter = ('time_serve',)
    search_fields = ('sub_cart__restaurant__name', 'food__name')

# Đăng ký các model
admin_site = MyAdminSite(name='admin')
admin_site.register(User, UserAdmin)
admin_site.register(Restaurant, RestaurantAdmin)
admin_site.register(Address, AddressAdmin)
admin_site.register(Tag, TagAdmin)
admin_site.register(Follow, FollowAdmin)
admin_site.register(Favorite, FavoriteAdmin)
admin_site.register(Order, OrderAdmin)
admin_site.register(OrderDetail, OrderDetailAdmin)
admin_site.register(Payment, PaymentAdmin)
admin_site.register(FoodCategory, FoodCategoryAdmin)
admin_site.register(Food, FoodAdmin)
admin_site.register(FoodPrice, FoodPriceAdmin)
admin_site.register(Menu, MenuAdmin)
admin_site.register(RestaurantReview, RestaurantReviewAdmin)
admin_site.register(FoodReview, FoodReviewAdmin)
admin_site.register(Cart, CartAdmin)
admin_site.register(SubCart, SubCartAdmin)
admin_site.register(SubCartItem, SubCartItemAdmin)