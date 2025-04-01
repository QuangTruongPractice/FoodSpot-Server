from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('orders', views.OrderViewSet)
router.register('order-detail', views.OrderDetailViewSet)
router.register('foods', views.FoodViewSet)
router.register('foods-category', views.FoodCategoryViewSet)
router.register('foods-review', views.FoodReviewViewSet)
router.register('restaurant-review', views.RestaurantReviewViewSet)
urlpatterns = [
    path('', include(router.urls))
]