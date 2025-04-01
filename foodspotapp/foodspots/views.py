from django.http import HttpResponse
from rest_framework import viewsets, permissions

from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview
from .serializers import (OrderSerializer, OrderDetailSerializer, FoodSerializers,
                          FoodCategorySerializer, FoodReviewSerializers, RestaurantReviewSerializer)


def index(request):
    return HttpResponse("foodspots")


class IsOrderOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Kiểm tra nếu obj là Order
        if isinstance(obj, Order):
            return obj.user == request.user
        # Kiểm tra nếu obj là OrderDetail
        elif isinstance(obj, OrderDetail):
            return obj.order.user == request.user
        return False

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderOwner]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        # Nếu request là lấy chi tiết 1 đơn hàng (retrieve), thêm order_details
        if self.action == 'retrieve':
            class OrderDetailWithItemsSerializer(OrderSerializer):
                order_details = OrderDetailSerializer(many=True, read_only=True)

                class Meta(OrderSerializer.Meta):
                    fields = OrderSerializer.Meta.fields + ['order_details']

            return OrderDetailWithItemsSerializer

        return OrderSerializer

class OrderDetailViewSet(viewsets.ModelViewSet):
    queryset = OrderDetail.objects.all()
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderOwner]

    def get_queryset(self):
        return OrderDetail.objects.filter(order__user=self.request.user).select_related('food')

class FoodViewSet(viewsets.ModelViewSet):
    queryset = Food.objects.all()
    serializer_class = FoodSerializers

class FoodCategoryViewSet(viewsets.ModelViewSet):
    queryset = FoodCategory.objects.all()
    serializer_class = FoodCategorySerializer

class FoodReviewViewSet(viewsets.ModelViewSet):
    queryset = FoodReview.objects.all()
    serializer_class = FoodReviewSerializers

class RestaurantReviewViewSet(viewsets.ModelViewSet):
    queryset = RestaurantReview.objects.all()
    serializer_class = RestaurantReviewSerializer