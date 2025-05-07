from django.contrib import admin
from .models import User, Restaurant, Food, FoodCategory, FoodPrice, Menu, Cart, SubCart, SubCartItem, Order, OrderDetail

class RestaurantAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    actions = ['approve_restaurants']

    def approve_restaurants(self, request, queryset):
        queryset.update(c=True)

        for r in queryset:
            email = r.owner.email
            if email:  # Kiểm tra xem owner có email không
                send_mail(
                    subject="Thông báo phê duyệt nhà hàng của bạn",
                    message=f"""
    Xin chào {r.owner},

    Nhà hàng "{r.name}" của bạn đã được xác thực thành công! 🎉
    Hãy đăng nhập bằng tài khoản và mật khẩu bạn đã đăng ký với chúng tôi.

    Cảm ơn bạn đã tham gia nền tảng của chúng tôi!

    Trân trọng,
    Đội ngũ quản trị.
    """,
                    from_email="lequoctrunggg@gmail.com",
                    recipient_list=[email],
                    fail_silently=False,
                )

        self.message_user(request, "Nhà hàng đã được phê duyệt!")

    approve_restaurants.short_description = "Phê duyệt nhà hàng đã chọn"


admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(User)
admin.site.register(Food)
admin.site.register(FoodCategory)
admin.site.register(FoodPrice)
admin.site.register(Menu)
admin.site.register(Cart)
admin.site.register(SubCart)
admin.site.register(SubCartItem)
admin.site.register(Order)
admin.site.register(OrderDetail)