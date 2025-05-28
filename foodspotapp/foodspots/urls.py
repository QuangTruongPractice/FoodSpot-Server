from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from .views import (
    RestaurantViewSet, UserViewSet, UserAddressViewSet,
    RestaurantAddressViewSet, SubCartViewSet, SubCartItemViewSet, MenuViewSet,
    CartViewSet, AddItemToCart, UpdateItemToSubCart, MomoPayment, CheckOrdered
)

router = DefaultRouter()
router.register('orders', views.OrderViewSet, basename='orders')
router.register('order-detail', views.OrderDetailViewSet, basename='order-detail')
router.register('foods', views.FoodViewSet, basename='foods')
router.register('foods-category', views.FoodCategoryViewSet, basename='foods-category')
router.register('foods-review', views.FoodReviewViewSet, basename='foods-review')
router.register('restaurant-review', views.RestaurantReviewViewSet, basename='restaurant-review')
router.register(r'restaurants', RestaurantViewSet, basename='restaurant')
router.register(r'users', UserViewSet, basename='user')
router.register(r'users-address', UserAddressViewSet, basename='user-address')
router.register(r'restaurant-address', RestaurantAddressViewSet, basename='restaurant-address')
router.register('cart', CartViewSet, basename='cart')
router.register(r'sub-cart', SubCartViewSet, basename='subcart')
router.register(r'sub-cart-item', SubCartItemViewSet, basename='subcartitem')
router.register(r'menus', MenuViewSet, basename='menu')

urlpatterns = [
    path('', include(router.urls)),
    path('add-to-cart/', AddItemToCart.as_view(), name='add-to-cart'),
    path('update-sub-cart-item/', UpdateItemToSubCart.as_view(), name='update-sub-cart-item'),
    path('momo-payment/', MomoPayment.as_view(), name='momo-payment'),
    path('check-ordered/', CheckOrdered.as_view(), name='check_ordered'),
]