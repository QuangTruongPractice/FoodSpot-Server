from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.db.models import Q, Prefetch
from rest_framework import viewsets, generics, mixins, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

import uuid, hmac, hashlib, requests

from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import (
    Order, OrderDetail, Food, FoodCategory, FoodReview,
    RestaurantReview, Restaurant, FoodPrice, Follow,
    Favorite, Cart, SubCart, SubCartItem, Payment,
    User, Address, Menu, TIME_SERVE_CHOICES
)

from .serializers import (
    OrderSerializer, OrderDetailSerializer, FoodSerializers, FoodCategorySerializer,
    FoodReviewSerializers, RestaurantReviewSerializer, FoodPriceSerializer,
    FollowSerializer, FavoriteSerializer, CartSerializer,
    SubCartSerializer, SubCartItemSerializer, UserSerializer,
    RestaurantSerializer, RestaurantAddressSerializer, AddressSerializer, UserAddressSerializer, MenuSerializer
)

from .perms import (
    IsAdminUser, IsOrderOwner, IsOwnerOrAdmin,
    IsRestaurantOwner, IsOwner, RestaurantOwner
)

from .paginators import (
    FoodPagination, OrderPagination, ReviewPagination,
)

def index(request):
    return HttpResponse("foodspots")


class OrderViewSet(viewsets.ViewSet):
    pagination_class = OrderPagination

    def get_permissions(self):
        if self.action in ['current_restaurant_orders', 'current_restaurant_order_details']:
            return [IsAuthenticated(), IsRestaurantOwner()]
        return [IsAuthenticated(), IsOrderOwner()]

    def get_object(self):
        return get_object_or_404(Order, pk=self.kwargs.get('pk'))

    def get_queryset(self):
        user = self.request.user
        if user.role == 'RESTAURANT_USER':
            return Order.objects.filter(restaurant__owner=user).order_by('-ordered_date', '-id')
        elif user.role == 'CUSTOMER':
            return Order.objects.filter(user=user).order_by('-ordered_date', '-id')
        return Order.objects.none()

    def list(self, request, *args, **kwargs):
        orders = self.get_queryset()
        paginator = self.pagination_class()
        paginated_orders = paginator.paginate_queryset(orders, request)
        serializer = OrderSerializer(paginated_orders, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        order = self.get_object()
        class OrderDetailWithItemsSerializer(OrderSerializer):
            order_details = OrderDetailSerializer(many=True, read_only=True)
            class Meta(OrderSerializer.Meta):
                fields = OrderSerializer.Meta.fields + ['order_details']
        return Response(OrderDetailWithItemsSerializer(order).data)

    def create(self, request, *args, **kwargs):
        order_serializer = OrderSerializer(data=request.data)
        if order_serializer.is_valid():
            order_serializer.save(user=request.user)
            return Response(order_serializer.data, status=status.HTTP_201_CREATED)
        return Response(order_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()
        status = request.data.get('status')
        if not status:
            return Response({"error": "Chỉ được cập nhật trạng thái đơn hàng."}, status=status.HTTP_400_BAD_REQUEST)
        order.status = status
        order.save()
        return Response(OrderSerializer(order).data)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.user != request.user and order.restaurant.owner != request.user:
            return Response({"detail": "Bạn không có quyền xóa đơn hàng này."}, status=status.HTTP_403_FORBIDDEN)
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['post'], detail=False, url_path='checkout')
    def checkout(self, request):
        user = self.request.user
        sub_cart_id = request.data.get("sub_cart_id")
        payment_method = request.data.get("payment_method")
        ship_fee = float(request.data.get('ship_fee'))
        total = float(request.data.get('total_price'))
        ship_address_id = int(request.data.get("ship_address_id"))

        sub_cart = get_object_or_404(SubCart, id=sub_cart_id)
        ship_address = get_object_or_404(Address, id=ship_address_id)
        cart = sub_cart.cart
        quantity = 0
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=user,
                    restaurant=sub_cart.restaurant,
                    address=ship_address,
                    shipping_fee=ship_fee,
                    total=total,
                )
                Payment.objects.create(
                    order=order,
                    total_payment=total,
                    payment_method=payment_method,
                )
                for s in sub_cart.sub_cart_items.all():
                    OrderDetail.objects.create(
                        food=s.food,
                        order=order,
                        quantity=s.quantity,
                        sub_total=s.price,
                        time_serve=s.time_serve
                    )
                    quantity += s.quantity
                sub_cart.delete()
                cart.item_number -= quantity
                cart.save()
                if cart.item_number == 0:
                    cart.delete()
                return Response({"message": "Đặt hàng thành công.", "order_id": order.id}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['get'], detail=False, url_path='current-restaurant-orders')
    def current_restaurant_orders(self, request):
        user = self.request.user
        if user.role != 'RESTAURANT_USER':
            return Response(
                {"error": "Chỉ người dùng có vai trò RESTAURANT_USER mới có thể xem đơn hàng của nhà hàng."},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            restaurant = Restaurant.objects.get(owner=user)
            orders = Order.objects.filter(restaurant=restaurant).order_by('-ordered_date', '-id')
            paginator = self.pagination_class()
            paginated_orders = paginator.paginate_queryset(orders, request)
            serializer = OrderSerializer(paginated_orders, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": "Người dùng này không sở hữu nhà hàng nào."},
                status=status.HTTP_404_NOT_FOUND
            )

class OrderDetailViewSet(viewsets.ModelViewSet):
    queryset = OrderDetail.objects.select_related('food')
    serializer_class = OrderDetailSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsOrderOwner()]

    @action(methods=['get'], detail=False, url_path='by-order/(?P<order_id>\d+)')
    def by_order(self, request, order_id=None):
        """
        Lấy tất cả OrderDetail theo ID của Order mà không sử dụng phân trang, hỗ trợ lọc theo food_id.
        """
        user = self.request.user
        order = get_object_or_404(Order, pk=order_id)

        # Kiểm tra quyền truy cập: người dùng phải là chủ đơn hàng hoặc chủ nhà hàng
        if order.user != user and order.restaurant.owner != user:
            logger.warning(f"User {user.id} does not have permission to view OrderDetails for order {order_id}")
            return Response(
                {"error": "Bạn không có quyền xem chi tiết đơn hàng này."},
                status=status.HTTP_403_FORBIDDEN
            )

        order_details = OrderDetail.objects.filter(
            order=order
        ).select_related('food').order_by('-id')

        # Lọc theo food_id
        food_id = request.query_params.get('food_id')
        if food_id:
            try:
                order_details = order_details.filter(food__id=int(food_id))
            except ValueError:
                return Response({"error": "food_id phải là một số nguyên."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(order_details, many=True, context={'request': request})
        logger.info(f"Retrieved {order_details.count()} OrderDetails for order {order_id}")
        return Response(serializer.data, status=status.HTTP_200_OK)
# class FoodPriceViewSet(viewsets.ModelViewSet):
#     queryset = FoodPrice.objects.select_related('food')
#     serializer_class = FoodPriceSerializer
#
#     def partial_update(self, request, *args, **kwargs):
#         if set(request.data.keys()) != {"price"}:
#             raise ValidationError({"detail": "Chỉ được phép cập nhật trường 'price'."})
#
#         instance = self.get_object()
#         serializer = self.get_serializer(instance, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         self.perform_update(serializer)
#         return Response(serializer.data)


from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
import logging

logger = logging.getLogger(__name__)


class FoodViewSet(viewsets.ViewSet, generics.ListAPIView, generics.RetrieveAPIView):
    serializer_class = FoodSerializers
    pagination_class = FoodPagination

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'add_price', 'update_price', 'delete_price']:
            return [IsAuthenticated(), IsRestaurantOwner()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = Food.objects.select_related(
            'food_category',
            'restaurant',
            'restaurant__owner'
        ).prefetch_related(
            Prefetch('prices', queryset=FoodPrice.objects.all())
        ).all().order_by('id')
        return self._apply_filters(queryset)

    def _apply_filters(self, queryset):
        params = self.request.query_params
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(restaurant__name__icontains=search)
            )
        food_category = params.get('food_category')
        if food_category:
            queryset = queryset.filter(food_category__name__icontains=food_category)
        category_id = params.get('category_id')
        if category_id:
            try:
                queryset = queryset.filter(food_category_id=int(category_id))
            except (ValueError, TypeError):
                logger.warning(f"Invalid category_id: {category_id}")
        restaurant_id = params.get('restaurant_id')
        if restaurant_id:
            try:
                queryset = queryset.filter(restaurant_id=int(restaurant_id))
            except (ValueError, TypeError):
                logger.warning(f"Invalid restaurant_id: {restaurant_id}")
        price_min = params.get('price_min')
        price_max = params.get('price_max')
        if price_min or price_max:
            queryset = self._filter_by_price_range(queryset, price_min, price_max)
        return queryset

    def create(self, request):
        # Loại bỏ trường prices nếu có trong dữ liệu để tránh lỗi validation
        data = request.data.copy()
        if 'prices' in data:
            data.pop('prices')

        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            logger.error(f"Food validation failed: {serializer.errors}")
            return Response({"error": "Dữ liệu không hợp lệ", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        restaurant_id = serializer.validated_data['restaurant'].id
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        try:
            with transaction.atomic():
                food = serializer.save()
            logger.info(f"Created food: {food.id} - {food.name}")
            return Response(self.get_serializer(food).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating food: {str(e)}")
            return Response(
                {"error": "Lỗi khi tạo món ăn.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, pk=None):
        food = get_object_or_404(Food, pk=pk)
        serializer = self.get_serializer(food, data=request.data)
        if not serializer.is_valid():
            logger.error(f"Food validation errors: {serializer.errors}")
            return Response({"error": "Dữ liệu không hợp lệ", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                food = serializer.save()
            logger.info(f"Updated food: {food.id} - {food.name}")
            return Response(self.get_serializer(food).data)
        except Exception as e:
            logger.error(f"Error updating food {pk}: {str(e)}")
            return Response(
                {"error": "Lỗi cập nhật món ăn.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def partial_update(self, request, pk=None):
        logger.info(f"Received PATCH request for food {pk} with data: {request.data}")
        food = get_object_or_404(Food, pk=pk)
        serializer = self.get_serializer(food, data=request.data, partial=True)
        if not serializer.is_valid():
            logger.error(f"Food validation errors: {serializer.errors}")
            return Response({"error": "Dữ liệu không hợp lệ", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                food = serializer.save()
            logger.info(f"Partially updated food: {food.id} - {food.name}")
            serializer = self.get_serializer(food)  # Serialize lại để trả về
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error partially updating food {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Lỗi cập nhật món ăn.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, pk=None):
        food = get_object_or_404(Food, pk=pk)
        food_name = food.name
        food.delete()
        logger.info(f"Deleted food: {pk} - {food_name}")
        return Response(
            {"message": "Món ăn đã được xóa thành công."},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        food = get_object_or_404(Food, pk=pk)
        reviews = FoodReview.objects.filter(
            order_detail__food=food,
            parent=None
        ).select_related(
            'user',
            'order_detail'
        ).prefetch_related(
            'replies'
        ).order_by('-created_at')
        serializer = FoodReviewSerializers(reviews, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        queryset = self.get_queryset()[:10]
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_price(self, request, pk=None):
        food = get_object_or_404(Food, pk=pk)
        serializer = FoodPriceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": "Dữ liệu giá không hợp lệ", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        if food.prices.filter(time_serve=serializer.validated_data['time_serve']).exists():
            return Response(
                {"error": "Thời gian phục vụ này đã có giá."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            food_price = serializer.save(food=food)
            logger.info(f"Added price for food {pk}: {food_price.time_serve} - {food_price.price}")
            return Response({
                "message": "Thêm giá thành công.",
                "price": {
                    "id": food_price.id,
                    "time_serve": food_price.time_serve,
                    "price": food_price.price
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error adding price for food {pk}: {str(e)}")
            return Response(
                {"error": "Lỗi thêm giá.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['put', 'patch'])
    def update_price(self, request, pk=None):
        food = get_object_or_404(Food, pk=pk)
        time_serve = request.data.get('time_serve')
        if not time_serve:
            return Response(
                {"error": "Cần cung cấp thời gian phục vụ."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            food_price = get_object_or_404(FoodPrice, food=food, time_serve=time_serve)
            serializer = FoodPriceSerializer(food_price, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response({"error": "Dữ liệu giá không hợp lệ", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            logger.info(f"Updated price for food {pk}: {time_serve} - {food_price.price}")
            return Response({
                "message": "Cập nhật giá thành công.",
                "price": {
                    "id": food_price.id,
                    "time_serve": food_price.time_serve,
                    "price": food_price.price
                }
            })
        except FoodPrice.DoesNotExist:
            return Response(
                {"error": "Không tìm thấy giá cho thời gian phục vụ này."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating price for food {pk}: {str(e)}")
            return Response(
                {"error": "Lỗi cập nhật giá.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_price(self, request, pk=None):
        food = get_object_or_404(Food, pk=pk)
        time_serve = request.query_params.get('time_serve')
        if not time_serve:
            return Response(
                {"error": "Cần cung cấp thời gian phục vụ để xóa."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            food_price = get_object_or_404(FoodPrice, food=food, time_serve=time_serve)
            if food.prices.count() <= 1:
                return Response(
                    {"error": "Không thể xóa giá cuối cùng. Món ăn phải có ít nhất một mức giá."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            food_price.delete()
            logger.info(f"Deleted price for food {pk}: {time_serve}")
            return Response(
                {"message": "Xóa giá thành công."},
                status=status.HTTP_204_NO_CONTENT
            )
        except FoodPrice.DoesNotExist:
            return Response(
                {"error": "Không tìm thấy giá cho thời gian phục vụ này."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting price for food {pk}: {str(e)}")
            return Response(
                {"error": "Lỗi xóa giá.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FoodCategoryViewSet(viewsets.ModelViewSet):
    queryset = FoodCategory.objects.all().order_by('id')
    serializer_class = FoodCategorySerializer

    def get_permissions(self):
        if self.action == 'list':  # Chỉ phương thức list mới được phép cho phép mọi người
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsAdminUser()]

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data
        if 'name' not in data:
            return Response(
                {"detail": "Chỉ có thể cập nhật tên của danh mục."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class BaseReviewUpdateMixin(viewsets.ViewSet):
    review_model = None
    review_serializer = None

    def get_permissions(self):
        if hasattr(self, 'action'):  # Kiểm tra xem action có tồn tại không
            if self.action == 'list':
                return [permissions.AllowAny()]
            elif self.action == 'create':
                return [permissions.IsAuthenticated(), IsOrderOwner()]
            elif self.action in ['update', 'partial_update', 'destroy']:
                return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        return super().get_permissions()

    def partial_update(self, request, pk=None):
        try:
            instance = self.review_model.objects.get(pk=pk)
        except self.review_model.DoesNotExist:
            return Response({"detail": "Không tìm thấy đánh giá."}, status=status.HTTP_404_NOT_FOUND)

        allowed_fields = {'comment'}
        invalid_fields = set(request.data.keys()) - allowed_fields
        if invalid_fields:
            return Response(
                {"detail": f"Chỉ có thể chỉnh sửa các trường: {', '.join(allowed_fields)}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.review_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class FoodReviewViewSet(BaseReviewUpdateMixin, viewsets.ViewSet,
                        generics.ListCreateAPIView, generics.RetrieveDestroyAPIView):
    queryset = FoodReview.objects.all()
    serializer_class = FoodReviewSerializers
    review_model = FoodReview
    review_serializer = FoodReviewSerializers

class RestaurantReviewViewSet(BaseReviewUpdateMixin, viewsets.ViewSet,
                              generics.ListCreateAPIView, generics.RetrieveDestroyAPIView):
    queryset = RestaurantReview.objects.all()
    serializer_class = RestaurantReviewSerializer
    review_model = RestaurantReview
    review_serializer = RestaurantReviewSerializer


class UserViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action in ['register_customer', 'register_restaurant']:
            return []
        return [IsAuthenticated()]

    def list(self, request):
        user = request.user
        if not (user.is_superuser or user.role == 'ADMIN'):
            return Response({"error": "Only superusers or admins can view the user list."},
                            status=status.HTTP_403_FORBIDDEN)

        queryset = User.objects.all()
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not (user.is_superuser or user.role == 'ADMIN' or user == target_user):
            return Response({"error": "You can only view your own details."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(target_user)
        return Response(serializer.data)

    @action(methods=['get', 'patch'], detail=False, url_path='current-user')
    def get_current_user(self, request):
        user = request.user
        if request.method == 'PATCH':
            serializer = UserSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserSerializer(user).data)

    def _create_user(self, request, validated_data, role, password):
        email = validated_data['email']
        if User.objects.filter(email=email).exists():
            print(f"Email {email} đã tồn tại.")
            return None, Response({"error": "Email đã được sử dụng."}, status=status.HTTP_400_BAD_REQUEST)

        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        validated_data['username'] = username

        validated_data['role'] = role
        validated_data['is_approved'] = (role != 'RESTAURANT_USER')

        validated_data.pop('password', None)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user, None

    @action(methods=['post'], detail=False, url_path='register-customer')
    def register_customer(self, request):
        print("Dữ liệu nhận được (CUSTOMER):", request.data)
        required_fields = ['email', 'password']
        for field in required_fields:
            if not request.data.get(field):
                return Response(
                    {"error": f"Trường {field} là bắt buộc."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = UserSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user, error_response = self._create_user(
                request,
                serializer.validated_data,
                role='CUSTOMER',
                password=request.data.get('password')
            )
            if error_response:
                return error_response

            response_data = UserSerializer(user, context={'request': request}).data
            response_data['message'] = "Đăng ký CUSTOMER thành công!"
            print("Đăng ký CUSTOMER thành công:", response_data)
            return Response(response_data, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
            print(f"IntegrityError occurred: {str(e)}")
            return Response({"error": "Email hoặc username đã tồn tại."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return Response(
                {"error": f"Đã xảy ra lỗi không mong muốn: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(methods=['post'], detail=False, url_path='register-restaurant')
    def register_restaurant(self, request):
        print("Dữ liệu nhận được (RESTAURANT):", request.data)
        required_fields = ['email', 'password', 'restaurant_name']
        for field in required_fields:
            if not request.data.get(field):
                return Response(
                    {"error": f"Trường {field} là bắt buộc."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = UserSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user, error_response = self._create_user(
                request,
                serializer.validated_data,
                role='RESTAURANT_USER',
                password=request.data.get('password')
            )
            if error_response:
                return error_response

            restaurant_name = request.data.get('restaurant_name').strip()
            if len(restaurant_name) < 3:
                user.delete()
                return Response(
                    {"error": "Tên nhà hàng phải có ít nhất 3 ký tự."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Với OneToOneField, kiểm tra xem user đã có nhà hàng chưa
            if hasattr(user, 'restaurant'):
                user.delete()
                return Response(
                    {"error": "Người dùng này đã sở hữu một nhà hàng. Mỗi người dùng chỉ được tạo một nhà hàng."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Restaurant.objects.create(name=restaurant_name, owner=user)

            response_data = UserSerializer(user, context={'request': request}).data
            response_data['message'] = "Tài khoản nhà hàng đã được tạo. Vui lòng chờ Admin phê duyệt."
            print("Đăng ký RESTAURANT thành công:", response_data)
            return Response(response_data, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
            print(f"IntegrityError occurred: {str(e)}")
            return Response({"error": "Email hoặc username đã tồn tại."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return Response(
                {"error": f"Đã xảy ra lỗi không mong muốn: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(methods=['get'], detail=False, url_path='current-user/follow')
    def current_user_followed_restaurants(self, request):
        user = request.user
        follows = Follow.objects.filter(user=user)
        serializer = FollowSerializer(follows, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=False, url_path='current-user/favorite')
    def current_user_favorite_restaurants(self, request):
        user = request.user
        favorites = Favorite.objects.filter(user=user)
        serializer = FavoriteSerializer(favorites, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=False, url_path='current-user/food-reviews')
    def current_user_food_reviews(self, request):
        user = request.user
        reviews = FoodReview.objects.filter(user=user)
        serializer = FoodReviewSerializers(reviews, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=False, url_path='current-user/restaurant')
    def get_user_restaurant(self, request):
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response(
                {"error": "Chỉ người dùng có vai trò RESTAURANT_USER mới có thể xem thông tin nhà hàng của mình."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            restaurant = Restaurant.objects.get(owner=user)
            serializer = RestaurantSerializer(restaurant, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": "Người dùng này không sở hữu nhà hàng nào."},
                status=status.HTTP_404_NOT_FOUND
            )


class UserAddressViewSet(viewsets.ViewSet):
    def get_permissions(self):
        return [IsAuthenticated()]

    def list(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Yêu cầu xác thực."}, status=status.HTTP_401_UNAUTHORIZED)
        if user.role not in ['ADMIN', 'CUSTOMER', 'RESTAURANT_USER']:
            return Response({"error": "Vai trò không hợp lệ."}, status=status.HTTP_403_FORBIDDEN)
        serializer = UserAddressSerializer(user)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        try:
            address = Address.objects.get(pk=pk)
        except Address.DoesNotExist:
            return Response({"error": "Không tìm thấy địa chỉ"}, status=status.HTTP_404_NOT_FOUND)

        if user.role != 'ADMIN' and address not in user.addresses.all():
            return Response({"error": "Bạn chỉ có thể xem địa chỉ của mình."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AddressSerializer(address)
        return Response(serializer.data)

    def create(self, request):
        user = request.user
        if user.role not in ['CUSTOMER', 'RESTAURANT_USER']:
            return Response({"error": "Chỉ khách hàng và người dùng nhà hàng có thể thêm địa chỉ."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AddressSerializer(data=request.data)
        if serializer.is_valid():
            address = serializer.save()
            user.addresses.add(address)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        user = request.user
        try:
            address = Address.objects.get(pk=pk)
        except Address.DoesNotExist:
            return Response({"error": "Không tìm thấy địa chỉ"}, status=status.HTTP_404_NOT_FOUND)

        if user.role != 'ADMIN' and address not in user.addresses.all():
            return Response({"error": "Bạn chỉ có thể cập nhật địa chỉ của mình."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AddressSerializer(address, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        user = request.user
        try:
            address = Address.objects.get(pk=pk)
        except Address.DoesNotExist:
            return Response({"error": "Không tìm thấy địa chỉ"}, status=status.HTTP_404_NOT_FOUND)

        if user.role != 'ADMIN' and address not in user.addresses.all():
            return Response({"error": "Bạn chỉ có thể xóa địa chỉ của mình."}, status=status.HTTP_403_FORBIDDEN)

        user.addresses.remove(address)
        if not address.users.exists() and not address.restaurants.exists():
            address.delete()  # Chỉ xóa nếu không có người dùng hoặc nhà hàng nào khác tham chiếu
        return Response({"message": "Địa chỉ đã được xóa thành công."}, status=status.HTTP_204_NO_CONTENT)

class RestaurantViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), RestaurantOwner()]
        return [AllowAny()]

    def list(self, request):
        queryset = Restaurant.objects.all()
        serializer = RestaurantSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            serializer = RestaurantSerializer(restaurant)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response({"error": "Only restaurant users can create a restaurant."}, status=status.HTTP_403_FORBIDDEN)

        # Với OneToOneField, kiểm tra xem user đã có nhà hàng chưa
        if hasattr(user, 'restaurant'):
            return Response(
                {"error": "Bạn đã sở hữu một nhà hàng. Mỗi người dùng chỉ được tạo một nhà hàng."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RestaurantSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner=user)  # Gán người tạo là owner
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            self.check_object_permissions(request, restaurant)  # Kiểm tra quyền
            serializer = RestaurantSerializer(restaurant, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            self.check_object_permissions(request, restaurant)  # Kiểm tra quyền
            serializer = RestaurantSerializer(restaurant, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            self.check_object_permissions(request, restaurant)  # Kiểm tra quyền
            restaurant.delete()
            return Response({"message": "Restaurant deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def menus(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            menus = Menu.objects.filter(restaurant=restaurant)  # Lọc các menu của nhà hàng
            serializer = MenuSerializer(menus, many=True)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def foods(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            foods = Food.objects.filter(restaurant=restaurant).order_by('-id')
            paginator = FoodPagination()
            result_page = paginator.paginate_queryset(foods, request)
            serializer = FoodSerializers(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            restaurant_reviews = RestaurantReview.objects.filter(restaurant=restaurant).order_by('-id')
            paginator = ReviewPagination()
            result_page = paginator.paginate_queryset(restaurant_reviews, request)
            serializer = RestaurantReviewSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)


class RestaurantAddressViewSet(viewsets.ViewSet):
    def get_permissions(self):
        return [AllowAny()]

    def list(self, request):
        queryset = Restaurant.objects.all()
        serializer = RestaurantAddressSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            serializer = RestaurantAddressSerializer(restaurant)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

class CartViewSet(viewsets.ViewSet, generics.DestroyAPIView):
    serializer_class = CartSerializer
    queryset = Cart.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    @action(methods=['get'], url_path='my-cart', detail=False)
    def get_my_cart(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response(
                {"message": "Giỏ hàng không tồn tại."},
                status=status.HTTP_200_OK
            )

        return Response(CartSerializer(cart).data)

    @action(methods=['get'], url_path='sub-carts', detail=False)
    def get_my_sub_cart(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response(
                {"message": "Giỏ hàng không tồn tại."},
                status=status.HTTP_200_OK
            )

        sub_carts = SubCart.objects.prefetch_related(
            Prefetch('sub_cart_items')
        ).filter(cart=cart)
        serializer = SubCartSerializer(sub_carts, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action in ['get_my_cart']:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

class SubCartViewSet(viewsets.ViewSet):
    serializer_class = SubCartSerializer
    queryset = SubCart.objects.all()
    def get_permissions(self):
        # Yêu cầu đăng nhập cho tất cả hành động vì giỏ hàng là dữ liệu cá nhân
        return [IsAuthenticated()]

    def list(self, request):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can view their sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        queryset = SubCart.objects.filter(cart__user=user)
        serializer = SubCartSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can view their sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        try:
            sub_cart = SubCart.objects.get(pk=pk, cart__user=user)
            serializer = SubCartSerializer(sub_cart)
            return Response(serializer.data)
        except SubCart.DoesNotExist:
            return Response({"error": "SubCart not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can create sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SubCartSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can delete their sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        try:
            sub_cart = SubCart.objects.get(pk=pk, cart__user=user)
            cart = sub_cart.cart
            sub_cart.delete()
            if not cart.sub_carts.exists():  # Kiểm tra nếu cart không còn sub_cart nào
                cart.delete()

            return Response({"message": "SubCart deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except SubCart.DoesNotExist:
            return Response({"error": "SubCart not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(methods=['get'], url_path='restaurant-sub-cart', detail=False)
    def get_sub_cart(self, request):
        restaurant_id = request.query_params.get('restaurantId')
        user_id = request.query_params.get('userId')

        cart = get_object_or_404(Cart, user__id=user_id)
        sub_cart = SubCart.objects.filter(cart__id=cart.id, restaurant__id=restaurant_id).first()

        if not sub_cart:
            return Response({"detail": "Không tìm thấy giỏ hàng"}, status=404)

        return Response(SubCartSerializer(sub_cart).data)

    @action(methods=['post'], url_path='delete-sub-carts', detail=False)
    def delete_multiple(self, request):
        cart_id = request.data.get('cartId')
        ids = request.data.get('ids', [])

        cart = get_object_or_404(Cart, pk=cart_id)
        if ids:
            ids = [int(id) for id in ids] #chuyen thanh int
            sub_carts_to_delete = SubCart.objects.filter(id__in=ids, cart=cart)
            # Cập nhật lại tổng số lượng sản phẩm trong Cart trước khi xóa
            total_quantity = 0
            for sub_cart in sub_carts_to_delete:
                total_quantity += sub_cart.total_quantity
            sub_carts_to_delete.delete()
            # Cập nhật lại item_number trong Cart
            cart.item_number -= total_quantity
            cart.save()
            # Nếu Cart không còn sản phẩm nào, xóa Cart
            if cart.item_number == 0:
                cart.delete()

        return Response({"message": "Xóa sub cart thành công!"}, status=status.HTTP_200_OK)

class SubCartItemViewSet(viewsets.ViewSet):
    serializer_class = SubCartItemSerializer
    queryset = SubCartItem.objects.all()
    def get_permissions(self):
        # Yêu cầu đăng nhập cho tất cả hành động vì liên quan đến giỏ hàng
        return [IsAuthenticated()]

    def list(self, request):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can view their sub-cart items."}, status=status.HTTP_403_FORBIDDEN)

        queryset = SubCartItem.objects.filter(sub_cart__cart__user=user)
        serializer = SubCartItemSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can view their sub-cart items."}, status=status.HTTP_403_FORBIDDEN)

        try:
            sub_cart_item = SubCartItem.objects.get(pk=pk, sub_cart__cart__user=user)
            serializer = SubCartItemSerializer(sub_cart_item)
            return Response(serializer.data)
        except SubCartItem.DoesNotExist:
            return Response({"error": "SubCartItem not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can add items to their sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SubCartItemSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can update their sub-cart items."}, status=status.HTTP_403_FORBIDDEN)

        try:
            sub_cart_item = SubCartItem.objects.get(pk=pk, sub_cart__cart__user=user)
            serializer = SubCartItemSerializer(sub_cart_item, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except SubCartItem.DoesNotExist:
            return Response({"error": "SubCartItem not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can delete their sub-cart items."}, status=status.HTTP_403_FORBIDDEN)

        try:
            sub_cart_item = SubCartItem.objects.get(pk=pk, sub_cart__cart__user=user)
            sub_cart = sub_cart_item.sub_cart  # Lưu lại sub_cart trước khi xóa
            cart = sub_cart.cart  # Lưu lại cart trước khi xóa
            sub_cart_item.delete()
            # Kiểm tra nếu SubCart không còn item nào thì xóa luôn SubCart
            if not sub_cart.sub_cart_items.exists():  # Kiểm tra nếu sub_cart không còn item nào
                sub_cart.delete()
                # Kiểm tra nếu Cart không còn SubCart nào thì xóa luôn Cart
                if not cart.sub_carts.exists():  # Kiểm tra nếu cart không còn sub_cart nào
                    cart.delete()

            return Response({"message": "SubCartItem and related SubCart and Cart deleted successfully."},
                            status=status.HTTP_204_NO_CONTENT)

        except SubCartItem.DoesNotExist:
            return Response({"error": "SubCartItem not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(methods=['post'], detail=False, url_path='delete-multiple')
    def delete_multiple(self, request):
        cart_id = request.data.get('cartId')
        ids = request.data.get('ids', [])

        cart = get_object_or_404(Cart, pk=cart_id)

        if ids:
            ids = [int(id) for id in ids]
            sub_cart_items_to_delete = SubCartItem.objects.filter(id__in=ids, sub_cart__cart=cart)

            for sub_cart_item in sub_cart_items_to_delete:
                sub_cart = sub_cart_item.sub_cart

                # Cập nhật sub_cart.total_quantity và total_price
                sub_cart.total_quantity -= sub_cart_item.quantity
                sub_cart.total_price -= sub_cart_item.quantity * sub_cart_item.price
                sub_cart.save()

                # Cập nhật cart.item_number
                cart.item_number -= sub_cart_item.quantity

                # Xóa SubCartItem
                sub_cart_item.delete()

                # Nếu sub_cart không còn item nào thì xóa
                if not sub_cart.sub_cart_items.exists():
                    sub_cart.delete()

            # Sau vòng lặp, nếu cart không còn sub_cart nào thì xóa luôn cart
            if not cart.sub_carts.exists():
                cart.delete()
            else:
                cart.save()

            return Response({"message": "Xóa SubCartItem thành công!"}, status=status.HTTP_200_OK)

        return Response({"error": "Danh sách ID rỗng!"}, status=status.HTTP_400_BAD_REQUEST)


class MenuViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def list(self, request):
        queryset = Menu.objects.all()
        serializer = MenuSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            menu = Menu.objects.get(pk=pk)
            serializer = MenuSerializer(menu)
            return Response(serializer.data)
        except Menu.DoesNotExist:
            return Response({"error": "Menu not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response({"error": "Only restaurant users can create menus."}, status=status.HTTP_403_FORBIDDEN)

        serializer = MenuSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            menu = serializer.save()
            # Kiểm tra xem nhà hàng có thuộc về user không
            if menu.restaurant.owner != user:
                menu.delete()
                return Response({"error": "You can only create menus for your own restaurant."}, status=status.HTTP_403_FORBIDDEN)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response({"error": "Only restaurant users can update menus."}, status=status.HTTP_403_FORBIDDEN)

        try:
            menu = Menu.objects.get(pk=pk)
            if menu.restaurant.owner != user:
                return Response({"error": "You can only update menus for your own restaurant."}, status=status.HTTP_403_FORBIDDEN)

            serializer = MenuSerializer(menu, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Menu.DoesNotExist:
            return Response({"error": "Menu not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response({"error": "Only restaurant users can delete menus."}, status=status.HTTP_403_FORBIDDEN)

        try:
            menu = Menu.objects.get(pk=pk)
            if menu.restaurant.owner != user:
                return Response({"error": "You can only delete menus for your own restaurant."}, status=status.HTTP_403_FORBIDDEN)

            menu.delete()
            return Response({"message": "Menu deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Menu.DoesNotExist:
            return Response({"error": "Menu not found"}, status=status.HTTP_404_NOT_FOUND)

class AddItemToCart(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        food_id = int(request.data.get('food_id'))
        time_serve = request.data.get('time_serve')
        quantity = 1

        # Lấy thực phẩm từ database
        food = get_object_or_404(Food, id=food_id)
        restaurant = food.restaurant

        # Lấy giá của thực phẩm cho thời gian phục vụ cụ thể

        cart, created = Cart.objects.get_or_create(user=user)

        sub_cart, created = SubCart.objects.get_or_create(cart=cart, restaurant=restaurant)
        # them hoac cap nhat
        sub_cart_item, created = SubCartItem.objects.get_or_create(
            food=food, sub_cart=sub_cart,
            defaults={'restaurant': restaurant,
                      'quantity': quantity,
                      'time_serve': time_serve,}
        )
        if not created:
            sub_cart_item.quantity += quantity
            sub_cart_item.save()

        # Update sub_cart
        sub_cart.total_price = sum(item.price for item in sub_cart.sub_cart_items.all())
        sub_cart.total_quantity = sum(item.quantity for item in sub_cart.sub_cart_items.all())
        sub_cart.save()

        # Update cart
        cart.total_price = sum(sub.total_price for sub in cart.sub_carts.all())
        cart.item_number = sum(sub.total_quantity for sub in cart.sub_carts.all())
        cart.save()

        return Response({'message': 'Thêm thành công!', 'cart': CartSerializer(cart).data}
                        , status=status.HTTP_200_OK)

class UpdateItemToSubCart(APIView):

    def patch(self, request, *args, **kwargs):
        sub_cart_item_id = int(request.data.get('sub_cart_item_id'))
        quantity = int(request.data.get('quantity'))
        sub_cart_item = get_object_or_404(SubCartItem, id=sub_cart_item_id)

        # Cập nhật SubCartItem
        sub_cart_item.quantity += quantity
        if sub_cart_item.quantity <= 0:
            sub_cart_item.delete()
        else:
            sub_cart_item.save()

        # Update sub_cart
        sub_cart = sub_cart_item.sub_cart
        sub_cart.total_price = sum(item.price for item in sub_cart.sub_cart_items.all())
        sub_cart.total_quantity = sum(item.quantity for item in sub_cart.sub_cart_items.all())
        if sub_cart.total_quantity <= 0:
            sub_cart.delete()
        else:
            sub_cart.save()

        # Update cart
        cart = sub_cart.cart
        cart.total_price = sum(sub.total_price for sub in cart.sub_carts.all())
        cart.item_number = sum(sub.total_quantity for sub in cart.sub_carts.all())
        if cart.item_number <= 0:
            cart.delete()
        else:
            cart.save()

        return Response({"message": "Cập nhật thành công."}, status=status.HTTP_200_OK)

class MomoPayment(APIView):
    def post(self, request):
        try:
            # Các tham số MoMo
            endpoint = "https://test-payment.momo.vn/v2/gateway/api/create"
            partnerCode = "MOMO"
            accessKey = "F8BBA842ECF85"
            secretKey = "K951B6PE1waDMi640xX08PD3vg6EkVlz"
            redirectUrl = "https://webhook.site/b3088a6a-2d17-4f8d-a383-71389a6c600b"
            ipnUrl = "https://webhook.site/b3088a6a-2d17-4f8d-a383-71389a6c600b"

            # Tham số từ người dùng
            amount = str(request.data.get('amount'))
            orderInfo = request.data.get('orderInfo', 'pay with MoMo')
            order_id = request.data.get('order_id')  #Lấy order_id từ client
            orderId = str(uuid.uuid4())
            requestId = str(uuid.uuid4())
            requestType = "captureWallet"
            extraData = ""

            # Tạo chữ ký
            raw_signature = f"accessKey={accessKey}&amount={amount}&extraData={extraData}&ipnUrl={ipnUrl}" \
                            f"&orderId={orderId}&orderInfo={orderInfo}&partnerCode={partnerCode}" \
                            f"&redirectUrl={redirectUrl}&requestId={requestId}&requestType={requestType}"
            h = hmac.new(bytes(secretKey, 'utf-8'), bytes(raw_signature, 'utf-8'), hashlib.sha256)
            signature = h.hexdigest()

            # Dữ liệu gửi đến MoMo
            data = {
                'partnerCode': partnerCode,
                'partnerName': "Test",
                'storeId': "MomoTestStore",
                'requestId': requestId,
                'amount': amount,
                'orderId': orderId,
                'orderInfo': orderInfo,
                'redirectUrl': redirectUrl,
                'ipnUrl': ipnUrl,
                'lang': "vi",
                'extraData': extraData,
                'requestType': requestType,
                'signature': signature
            }

            # Gửi yêu cầu đến MoMo
            response = requests.post(endpoint, json=data, headers={'Content-Type': 'application/json'})
            momo_response = response.json()

            # Giả sử thanh toán thành công => cập nhật trạng thái thanh toán
            if momo_response.get('resultCode') == 0:
                payment = Payment.objects.get(order_id=order_id)
                payment.status = 'SUCCESS'  # nhớ cập nhật field status trong model Payment
                payment.save()

            return Response(momo_response, status=response.status_code)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CheckOrdered(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        restaurant_id = request.query_params.get("restaurant_id")

        if not restaurant_id:
            return Response(
                {"error": "restaurant_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        has_ordered = Order.objects.filter(user=request.user, restaurant_id=restaurant_id).exists()
        return Response({"has_ordered": has_ordered})