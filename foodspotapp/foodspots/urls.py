from django.urls import path, include
from rest_framework.routers import DefaultRouter
from foodspots.views import (
    RestaurantViewSet, UserViewSet, UserAddressViewSet,
    RestaurantAddressViewSet, SubCartViewSet, SubCartItemViewSet, MenuViewSet
)

router = DefaultRouter()
router.register(r'restaurants', RestaurantViewSet, basename='restaurant')
router.register(r'users', UserViewSet, basename='user')
router.register(r'users-address', UserAddressViewSet, basename='user-address')
router.register(r'restaurant-address', RestaurantAddressViewSet, basename='restaurant-address')
router.register(r'sub-cart', SubCartViewSet, basename='subcart')
router.register(r'sub-cart-item', SubCartItemViewSet, basename='subcartitem')
router.register(r'menus', MenuViewSet, basename='menu')

urlpatterns = [
    path('', include(router.urls)),
]