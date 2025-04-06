from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action

from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview, Restaurant
from .serializers import (OrderSerializer, OrderDetailSerializer, FoodSerializers,
                          FoodCategorySerializer, FoodReviewSerializers, RestaurantReviewSerializer,
                          FoodDetailSerializers)


def index(request):
    return HttpResponse("foodspots")


class IsOrderOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Order):
            return obj.user == request.user or (
                request.user.role == 'RESTAURANT_USER' and obj.restaurant.owner == request.user
            )
        return False

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderOwner]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'RESTAURANT_USER':
            return Order.objects.filter(restaurant__owner=user)
        return Order.objects.filter(user=user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            class OrderDetailWithItemsSerializer(OrderSerializer):
                order_details = OrderDetailSerializer(many=True, read_only=True)
                class Meta(OrderSerializer.Meta):
                    fields = OrderSerializer.Meta.fields + ['order_details']
            return OrderDetailWithItemsSerializer
        return OrderSerializer

# Phương thức POST tạo mới Order
    def create(self, request, *args, **kwargs):
        # Thực hiện logic tạo mới Order ở đây, ví dụ:
        order_serializer = self.get_serializer(data=request.data)
        if order_serializer.is_valid():
            order_serializer.save(user=request.user)  # Lưu Order và gán người dùng hiện tại
            return Response(order_serializer.data, status=status.HTTP_201_CREATED)
        return Response(order_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        """Chỉ cho phép cập nhật trạng thái đơn hàng và phương thức thanh toán"""
        order = self.get_object()
        data = request.data

        allowed_fields = ["status", "payment_method", "payment_status"]
        update_data = {key: value for key, value in data.items() if key in allowed_fields}

        if not update_data:
            return Response({"error": "Chỉ được cập nhật trạng thái đơn hàng hoặc phương thức thanh toán."},
                            status=status.HTTP_400_BAD_REQUEST)

        for field, value in update_data.items():
            setattr(order, field, value)  # Cập nhật trường tương ứng trong order
        order.save()  # Lưu đối tượng

        return Response(self.get_serializer(order).data)


class OrderDetailViewSet(viewsets.ModelViewSet):
    queryset = OrderDetail.objects.all()
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderOwner]

    def get_queryset(self):
        return OrderDetail.objects.filter(order__user=self.request.user).select_related('food')

class FoodViewSet(viewsets.ModelViewSet):
    queryset = Food.objects.prefetch_related('menus__restaurant').all()
    serializer_class = FoodSerializers

    def get_queryset(self):
        queryset = super().get_queryset()

        name = self.request.query_params.get('name', None)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)

        price_min = self.request.query_params.get('price_min', None)
        price_max = self.request.query_params.get('price_max', None)
        if price_min is not None:
            queryset = queryset.filter(price__gte=price_min)
        if price_max is not None:
            queryset = queryset.filter(price__lte=price_max)

        food_category = self.request.query_params.get('food_category', None)
        if food_category is not None:
            queryset = queryset.filter(food_category__name__icontains=food_category)

        restaurant_name = self.request.query_params.get('restaurant_name', None)
        if restaurant_name is not None:
            queryset = queryset.filter(menus__restaurant__name__icontains=restaurant_name)

        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':  # Khi gọi `api/foods/{food_id}/`
            return FoodDetailSerializers
        return FoodSerializers

class FoodCategoryViewSet(viewsets.ModelViewSet):
    queryset = FoodCategory.objects.all()
    serializer_class = FoodCategorySerializer

class FoodReviewViewSet(viewsets.ModelViewSet):
    queryset = FoodReview.objects.all()
    serializer_class = FoodReviewSerializers

class RestaurantReviewViewSet(viewsets.ModelViewSet):
    queryset = RestaurantReview.objects.all()
    serializer_class = RestaurantReviewSerializer