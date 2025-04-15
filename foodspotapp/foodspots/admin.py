from django.contrib import admin
from .models import User, Restaurant, Food, FoodCategory, FoodPrice, Menu, Cart, SubCart, SubCartItem, Order, OrderDetail

# Register your models here.
admin.site.register(Restaurant)
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
