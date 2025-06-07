from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError, models
from django.db.models import Q, Prefetch, Sum, Count
from django.core.mail import send_mail
from django.conf import settings

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
    User, Address, Menu, Notification
)

from .serializers import (
    OrderSerializer, OrderDetailSerializer, FoodSerializers, FoodCategorySerializer,
    FoodReviewSerializers, RestaurantReviewSerializer, FoodPriceSerializer,
    FollowSerializer, FavoriteSerializer, CartSerializer,
    SubCartSerializer, SubCartItemSerializer, UserSerializer,
    RestaurantSerializer, RestaurantAddressSerializer, AddressSerializer,
    UserAddressSerializer, MenuSerializer, NotificationSerializer
)

from .perms import (
    IsAdminUser, IsOrderOwner, IsOwnerOrAdmin,
    IsRestaurantOwner, IsOwner, RestaurantOwner
)

from .paginators import (
    FoodPagination, OrderPagination, ReviewPagination, NotificationPagination
)

from datetime import datetime, date
from calendar import monthrange
from threading import Thread
from .services import notify_new_food, notify_new_menu
import re
from cloudinary.uploader import upload

import logging
logger = logging.getLogger(__name__)

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
        # Áp dụng phân trang
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

    @action(methods=['post'], detail=False, url_path='checkout')
    def checkout(self, request):
        user = request.user
        sub_cart_id = request.data.get("sub_cart_id")
        payment_method = request.data.get("payment_method")
        ship_fee = float(request.data.get('ship_fee'))
        total = float(request.data.get('total_price'))  # da bao gom phi ship
        ship_address_id = int(request.data.get("ship_address_id"))  # dia chi nguoi dung

        sub_cart = get_object_or_404(SubCart, id=sub_cart_id)
        print(sub_cart)
        ship_address = get_object_or_404(Address, id=ship_address_id)
        print(ship_address)
        cart = sub_cart.cart
        quantity = 0
        try:
            with transaction.atomic():
                order = Order.objects.create(user=user,
                                             restaurant=sub_cart.restaurant,
                                             address=ship_address,
                                             shipping_fee=ship_fee,
                                             total=total, )

                Payment.objects.create(order=order,
                                       total_payment=total,
                                       payment_method=payment_method, )

                for s in sub_cart.sub_cart_items.all():
                    OrderDetail.objects.create(food=s.food,
                                               order=order,
                                               quantity=s.quantity,
                                               sub_total=s.price,
                                               time_serve=s.time_serve)
                    quantity += s.quantity

                sub_cart.delete()
                cart.item_number -= quantity

                cart.save()
                if cart.item_number == 0:
                    cart.delete()

                return Response({"message": "Đặt hàng thành công.",
                                 "order_id": order.id}, status=status.HTTP_200_OK)

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


class OrderDetailViewSet(viewsets.ViewSet, generics.ListAPIView, generics.RetrieveAPIView):
    queryset = OrderDetail.objects.select_related('food').all()
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsOrderOwner]

    @action(methods=['get'], detail=False, url_path='by-order/(?P<order_id>\d+)')
    def by_order(self, request, order_id=None):
        user = self.request.user
        order = get_object_or_404(Order, pk=order_id)
        if order.user != user and order.restaurant.owner != user:
            logger.warning(f"User {user.id} does not have permission to view OrderDetails for order {order_id}")
            return Response(
                {"error": "Bạn không có quyền xem chi tiết đơn hàng này."},
                status=status.HTTP_403_FORBIDDEN
            )
        order_details = OrderDetail.objects.filter(
            order=order
        ).select_related('food').order_by('-id')

        food_id = request.query_params.get('food_id')
        if food_id:
            try:
                order_details = order_details.filter(food__id=int(food_id))
            except ValueError:
                return Response({"error": "food_id phải là một số nguyên."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(order_details, many=True, context={'request': request})
        logger.info(f"Retrieved {order_details.count()} OrderDetails for order {order_id}")

        return Response(serializer.data, status=status.HTTP_200_OK)

class FoodPriceViewSet(viewsets.ModelViewSet):
    queryset = FoodPrice.objects.select_related('food')
    serializer_class = FoodPriceSerializer

    def partial_update(self, request, *args, **kwargs):
        if set(request.data.keys()) != {"price"}:
            raise ValidationError({"detail": "Chỉ được phép cập nhật trường 'price'."})

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class FoodViewSet(viewsets.ModelViewSet):
    serializer_class = FoodSerializers
    pagination_class = FoodPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        else:
            return [IsAuthenticated(), IsRestaurantOwner()]

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
        price_min = self.request.query_params.get('price_min')
        price_max = self.request.query_params.get('price_max')

        if price_min or price_max:
            food_prices = FoodPrice.objects.all()
            if price_min:
                food_prices = food_prices.filter(price__gte=price_min)
            if price_max:
                food_prices = food_prices.filter(price__lte=price_max)
            queryset = queryset.filter(id__in=food_prices.values('food_id')).distinct()
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            # Debug: In ra để kiểm tra
            print(f"request.data: {request.data}")
            print(f"request.FILES: {request.FILES}")

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            food = serializer.save()

            Thread(target=send_notification_async, args=(food,)).start()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"Error creating food: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            data = request.data

            # Cập nhật dữ liệu
            serializer = self.get_serializer(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            food = serializer.save()

            # Gửi thông báo bất đồng bộ nếu có thay đổi
            if any(field in data for field in ['name', 'price', 'description', 'image']):
                Thread(target=send_notification_async, args=(food,)).start()

            return Response(serializer.data)
        except Exception as e:
            print(f"Error updating food: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        try:
            food = Food.objects.get(pk=pk)
            food_reviews = FoodReview.objects.filter(order_detail__food=food, parent=None).order_by('-id')
            paginator = ReviewPagination()
            paginated_reviews = paginator.paginate_queryset(food_reviews, request)
            serializer = FoodReviewSerializers(paginated_reviews, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Food.DoesNotExist:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)

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
            return Response({"error": "Dữ liệu giá không hợp lệ", "details": serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)
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
                return Response({"error": "Dữ liệu giá không hợp lệ", "details": serializer.errors},
                                status=status.HTTP_400_BAD_REQUEST)
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
        if hasattr(self, 'action'):
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

        if self.action == 'current_user_followed_restaurants':
            if self.request.method == 'GET':
                return [permissions.IsAuthenticated()]
            elif self.request.method == 'POST':
                return [permissions.IsAuthenticated(), IsOwner()]

        if self.action == 'current_user_favorite_foods':
            if self.request.method == 'GET':
                return [permissions.IsAuthenticated()]
            elif self.request.method == 'POST':
                return [permissions.IsAuthenticated(), IsOwner()]

        return [permissions.IsAuthenticated()]

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

        if not (user.is_superuser or user.role == 'ADMIN' or user.role == 'RESTAURANT_USER' or user == target_user):
            return Response({"error": "You can only view your own details."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(target_user)
        return Response(serializer.data)

    @action(methods=['get', 'patch'], detail=False, url_path='current-user')
    def get_current_user(self, request):
        user = request.user
        if request.method == 'PATCH':
            serializer = UserSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                try:
                    serializer.save()
                    return Response(serializer.data)
                except Exception as e:
                    return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserSerializer(user).data)

    def _create_user(self, request, validated_data, role, password):
        email = validated_data['email']
        if User.objects.filter(email=email).exists():
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
        print("validated_data trước khi tạo User:", validated_data)

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

    @action(methods=['get', 'post'], detail=False, url_path='current-user/follow')
    def current_user_followed_restaurants(self, request):
        user = request.user
        if request.method == 'GET':
            follows = Follow.objects.filter(user=user)
            serializer = FollowSerializer(follows, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            restaurant_id = request.data.get('restaurant')
            status_value = request.data.get('status')

            restaurant = get_object_or_404(Restaurant, pk=restaurant_id)

            follow, created = Follow.objects.get_or_create(
                user=user,
                restaurant=restaurant,
                defaults={'status': status_value}
            )

            if not created and status_value is not None:
                follow.status = status_value
                follow.save()

            serializer = FollowSerializer(follow)
            return Response(serializer.data)

    @action(methods=['get', 'post'], detail=False, url_path='current-user/favorite')
    def current_user_favorite_foods(self, request):
        user = request.user
        if request.method == 'GET':
            favorites = Favorite.objects.filter(user=user)
            serializer = FavoriteSerializer(favorites, many=True)
            return Response(serializer.data)
        elif request.method == 'POST':
            food_id = request.data.get('food')
            status_value = request.data.get('status')

            food = get_object_or_404(Food, pk=food_id)

            fav, created = Favorite.objects.get_or_create(
                user=user,
                food=food,
                defaults={'status': status_value}
            )

            if not created and status_value is not None:
                fav.status = status_value
                fav.save()

            serializer = FavoriteSerializer(fav)
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
        return Response(status=status.HTTP_204_NO_CONTENT)

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
    permission_classes = [permissions.IsAuthenticated]

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
    permission_classes = [permissions.IsAuthenticated]

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
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'add_food_to_menu']:
            return [permissions.IsAuthenticated(), RestaurantOwner()]
        return [permissions.AllowAny()]

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
        logger.info(f"Request data: {request.data}")
        restaurant_id = request.data.get('restaurant')
        if restaurant_id is None:
            logger.error("Missing restaurant field in request data")
            return Response(
                {"restaurant": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            restaurant_id = int(restaurant_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid restaurant ID: {restaurant_id}")
            return Response(
                {"restaurant": ["Invalid restaurant ID. Must be an integer."]},
                status=status.HTTP_400_BAD_REQUEST
            )
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        logger.info(f"Found restaurant: {restaurant.id} - {restaurant.name}")
        data = request.data.copy()
        data.pop('restaurant', None)
        serializer = MenuSerializer(data=data)
        if serializer.is_valid():
            self.perform_create(serializer, restaurant=restaurant)
            logger.info(f"Created menu: {serializer.data.get('name')}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)  # Bỏ headers
        logger.error(f"Serializer errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer, restaurant=None):
        if restaurant is None:
            logger.error("Restaurant is None in perform_create")
            raise ValueError("Restaurant cannot be None")
        menu = serializer.save(restaurant=restaurant)
        notify_new_menu(menu)

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

    def patch(self, request, pk=None):
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response({"error": "Chỉ người dùng nhà hàng mới có thể cập nhật menu."}, status=status.HTTP_403_FORBIDDEN)

        try:
            menu = Menu.objects.get(pk=pk)
            if menu.restaurant.owner != user:
                return Response({"error": "Bạn chỉ có thể cập nhật menu của nhà hàng của mình."}, status=status.HTTP_403_FORBIDDEN)

            serializer = MenuSerializer(menu, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Menu {pk} được cập nhật bởi người dùng {user.id}")
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Menu.DoesNotExist:
            return Response({"error": "Không tìm thấy menu."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật menu {pk}: {str(e)}")
            return Response(
                {"error": "Đã xảy ra lỗi khi cập nhật menu.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

    @action(detail=True, methods=['post'], url_path='add-food')
    def add_food_to_menu(self, request, pk=None):
        user = request.user
        try:
            menu = Menu.objects.get(pk=pk)
            # Kiểm tra xem người dùng có sở hữu nhà hàng liên quan đến menu không
            if menu.restaurant.owner != user:
                return Response(
                    {"error": "Bạn chỉ có thể thêm món ăn vào menu của nhà hàng của mình."},
                    status=status.HTTP_403_FORBIDDEN
                )

            food_id = request.data.get('food_id')
            if not food_id:
                return Response(
                    {"error": "Cần cung cấp food_id."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            food = get_object_or_404(Food, pk=food_id)
            # Kiểm tra xem món ăn có thuộc về cùng nhà hàng với menu không
            if food.restaurant != menu.restaurant:
                return Response(
                    {"error": "Món ăn phải thuộc về cùng nhà hàng với menu."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Thêm món ăn vào menu
            menu.foods.add(food)
            logger.info(f"Đã thêm món ăn {food_id} vào menu {pk} bởi người dùng {user.id}")
            return Response(
                {"message": f"Món ăn {food.name} đã được thêm vào menu {menu.name} thành công."},
                status=status.HTTP_200_OK
            )

        except Menu.DoesNotExist:
            return Response(
                {"error": "Không tìm thấy menu."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Lỗi khi thêm món ăn vào menu {pk}: {str(e)}")
            return Response(
                {"error": "Đã xảy ra lỗi khi thêm món ăn vào menu.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='foods')
    def get_menu_foods(self, request, pk=None):
        try:
            menu = get_object_or_404(Menu, pk=pk)
            foods = menu.foods.all().select_related('food_category', 'restaurant').prefetch_related('prices').order_by('id')
            paginator = FoodPagination()
            result_page = paginator.paginate_queryset(foods, request)
            serializer = FoodSerializers(result_page, many=True, context={'request': request})
            logger.info(f"Retrieved {foods.count()} foods for menu {pk}")
            return paginator.get_paginated_response(serializer.data)
        except Menu.DoesNotExist:
            logger.warning(f"Menu {pk} not found")
            return Response({"error": "Menu not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving foods for menu {pk}: {str(e)}")
            return Response(
                {"error": "Error retrieving menu foods", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
            redirectUrl = 'foodspot://payment-result'
            ipnUrl = "https://7082-2405-4802-9111-2a0-303e-3c97-d01f-3c5c.ngrok-free.app/momo-callback/"

            # Tham số từ người dùng
            amount = str(request.data.get('amount'))
            orderInfo = request.data.get('orderInfo', 'pay with MoMo')
            orderId = str(uuid.uuid4())
            requestId = str(uuid.uuid4())
            requestType = "captureWallet"
            extraData = request.data.get('order_id')

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
            print(momo_response)

            return Response(momo_response, status=response.status_code)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class MomoCallback(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        print("CAllBack:::")
        try:
            data = request.data
            print("Dữ liệu từ MoMo gửi về:", data)
            # Xử lý kết quả thanh toán
            order_id = data.get('extraData')
            print(order_id)
            result_code = data.get('resultCode')

            try:
                payment = Payment.objects.get(order_id=order_id)
                if result_code == 0:
                    payment.status = 'SUCCESS'
                else:
                    payment.status = 'FAIL'
                payment.save()
            except Payment.DoesNotExist:
                return Response({'message': 'Order not found'}, status=404)

            return Response({'message': 'Callback received successfully'}, status=200)

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

class CheckOwnerRestaurant(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == 'RESTAURANT_USER':
            restaurant = Restaurant.objects.filter(owner=user).first()
            if restaurant:
                return Response({'restaurant_id': restaurant.id})

        return Response({})

class RestaurantRevenueStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_period(self, period_str):
        period_str = period_str.strip()

        # Match month/year format (5/2025, 05/2025)
        month_year_pattern = r'^(\d{1,2})/(\d{4})$'
        match = re.match(month_year_pattern, period_str)
        if match:
            month = int(match.group(1))
            year = int(match.group(2))
            if not (1 <= month <= 12):
                raise ValidationError("Month must be between 1 and 12")

            start_date = date(year, month, 1)
            _, last_day = monthrange(year, month)
            end_date = date(year, month, last_day)
            return start_date, end_date, f"Tháng {month}/{year}"

        # Match quarter format (Q1 2025, q1 2025)
        quarter_pattern = r'^[Qq]([1-4])\s+(\d{4})$'
        match = re.match(quarter_pattern, period_str)
        if match:
            quarter = int(match.group(1))
            year = int(match.group(2))

            quarter_months = {
                1: (1, 3),   # Q1: Jan-Mar
                2: (4, 6),   # Q2: Apr-Jun
                3: (7, 9),   # Q3: Jul-Sep
                4: (10, 12)  # Q4: Oct-Dec
            }

            start_month, end_month = quarter_months[quarter]
            start_date = date(year, start_month, 1)
            _, last_day = monthrange(year, end_month)
            end_date = date(year, end_month, last_day)
            return start_date, end_date, f"Quý {quarter}/{year}"

        # Match year format (2025)
        year_pattern = r'^(\d{4})$'
        match = re.match(year_pattern, period_str)
        if match:
            year = int(match.group(1))
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            return start_date, end_date, f"Năm {year}"

        raise ValidationError("Invalid period format. Use formats like '5/2025', 'Q1 2025', or '2025'")

    def get_restaurant(self, restaurant_id):
        try:
            return Restaurant.objects.get(id=restaurant_id)
        except Restaurant.DoesNotExist:
            return None

    def get_order_details(self, restaurant, start_date, end_date):
        return OrderDetail.objects.filter(
            order__restaurant=restaurant,
            order__ordered_date__gte=start_date,
            order__ordered_date__lte=end_date,
            order__status__in=['ACCEPTED', 'DELIVERED']  # Only successful orders
        ).select_related('food', 'food__food_category', 'order')


class FoodRevenueStatisticsView(RestaurantRevenueStatisticsView):

    def get(self, request, restaurant_id):
        try:
            # Validate restaurant exists
            restaurant = self.get_restaurant(restaurant_id)
            if not restaurant:
                return Response({
                    'error': 'Restaurant not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if user has permission to view this restaurant's data
            if (request.user.role == 'RESTAURANT_USER' and
                    hasattr(request.user, 'restaurants') and
                    request.user.restaurants.id != restaurant.id):
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)

            # Get period parameter
            period = request.query_params.get('period')
            if not period:
                return Response({
                    'error': 'Period parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                start_date, end_date, period_display = self.parse_period(period)
            except ValidationError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get order details for the restaurant in the specified period
            order_details = self.get_order_details(restaurant, start_date, end_date)

            # Group by food and calculate revenue
            food_stats = {}
            for detail in order_details:
                food_id = detail.food.id
                if food_id not in food_stats:
                    food_stats[food_id] = {
                        'food_id': food_id,
                        'food_name': detail.food.name,
                        'category': detail.food.food_category.name,
                        'total_quantity': 0,
                        'total_revenue': 0,
                        'order_count': set(),
                        'avg_price': 0
                    }

                food_stats[food_id]['total_quantity'] += detail.quantity
                food_stats[food_id]['total_revenue'] += detail.sub_total
                food_stats[food_id]['order_count'].add(detail.order.id)

            # Convert sets to counts and calculate averages
            food_revenue_list = []
            for stats in food_stats.values():
                stats['order_count'] = len(stats['order_count'])
                stats['avg_price'] = round(stats['total_revenue'] / stats['total_quantity'], 2) if stats['total_quantity'] > 0 else 0
                stats['total_revenue'] = round(stats['total_revenue'], 2)
                food_revenue_list.append(stats)

            # Sort by total revenue (descending)
            food_revenue_list.sort(key=lambda x: x['total_revenue'], reverse=True)

            # Calculate totals
            total_revenue = sum(item['total_revenue'] for item in food_revenue_list)
            total_quantity = sum(item['total_quantity'] for item in food_revenue_list)
            total_orders = len(set(detail.order.id for detail in order_details))

            return Response({
                'success': True,
                'data': {
                    'restaurant_id': restaurant_id,
                    'restaurant_name': restaurant.name,
                    'period': period_display,
                    'period_range': {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    },
                    'summary': {
                        'total_revenue': round(total_revenue, 2),
                        'total_quantity': total_quantity,
                        'total_orders': total_orders,
                        'total_foods': len(food_revenue_list),
                        'avg_order_value': round(total_revenue / total_orders, 2) if total_orders > 0 else 0
                    },
                    'food_revenue': food_revenue_list
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'An error occurred: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CategoryRevenueStatisticsView(RestaurantRevenueStatisticsView):
    def get(self, request, restaurant_id):
        try:
            # Validate restaurant exists
            restaurant = self.get_restaurant(restaurant_id)
            if not restaurant:
                return Response({
                    'error': 'Restaurant not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if user has permission to view this restaurant's data
            if (request.user.role == 'RESTAURANT_USER' and
                    hasattr(request.user, 'restaurants') and
                    request.user.restaurants.id != restaurant.id):
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)

            # Get period parameter
            period = request.query_params.get('period')
            if not period:
                return Response({
                    'error': 'Period parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                start_date, end_date, period_display = self.parse_period(period)
            except ValidationError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get order details for the restaurant in the specified period
            order_details = self.get_order_details(restaurant, start_date, end_date)

            # Group by category and calculate revenue
            category_stats = {}
            for detail in order_details:
                category_id = detail.food.food_category.id
                category_name = detail.food.food_category.name

                if category_id not in category_stats:
                    category_stats[category_id] = {
                        'category_id': category_id,
                        'category_name': category_name,
                        'total_quantity': 0,
                        'total_revenue': 0,
                        'food_count': set(),
                        'order_count': set(),
                        'foods': {}
                    }

                category_stats[category_id]['total_quantity'] += detail.quantity
                category_stats[category_id]['total_revenue'] += detail.sub_total
                category_stats[category_id]['food_count'].add(detail.food.id)
                category_stats[category_id]['order_count'].add(detail.order.id)

                # Track individual food performance within category
                food_id = detail.food.id
                if food_id not in category_stats[category_id]['foods']:
                    category_stats[category_id]['foods'][food_id] = {
                        'food_id': food_id,
                        'food_name': detail.food.name,
                        'quantity': 0,
                        'revenue': 0
                    }

                category_stats[category_id]['foods'][food_id]['quantity'] += detail.quantity
                category_stats[category_id]['foods'][food_id]['revenue'] += detail.sub_total

            # Convert sets to counts and prepare final data
            category_revenue_list = []
            for stats in category_stats.values():
                stats['food_count'] = len(stats['food_count'])
                stats['order_count'] = len(stats['order_count'])
                stats['avg_revenue_per_food'] = round(stats['total_revenue'] / stats['food_count'], 2) if stats['food_count'] > 0 else 0
                stats['total_revenue'] = round(stats['total_revenue'], 2)

                # Convert foods dict to list and sort by revenue
                foods_list = list(stats['foods'].values())
                for food in foods_list:
                    food['revenue'] = round(food['revenue'], 2)
                foods_list.sort(key=lambda x: x['revenue'], reverse=True)
                stats['top_foods'] = foods_list[:5]  # Top 5 foods in category

                del stats['foods']  # Remove the dict version
                category_revenue_list.append(stats)

            # Sort by total revenue (descending)
            category_revenue_list.sort(key=lambda x: x['total_revenue'], reverse=True)

            # Calculate totals
            total_revenue = sum(item['total_revenue'] for item in category_revenue_list)
            total_quantity = sum(item['total_quantity'] for item in category_revenue_list)
            total_orders = len(set(detail.order.id for detail in order_details))
            total_categories = len(category_revenue_list)

            return Response({
                'success': True,
                'data': {
                    'restaurant_id': restaurant_id,
                    'restaurant_name': restaurant.name,
                    'period': period_display,
                    'period_range': {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    },
                    'summary': {
                        'total_revenue': round(total_revenue, 2),
                        'total_quantity': total_quantity,
                        'total_orders': total_orders,
                        'total_categories': total_categories,
                        'avg_order_value': round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
                        'avg_revenue_per_category': round(total_revenue / total_categories, 2) if total_categories > 0 else 0
                    },
                    'category_revenue': category_revenue_list
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'An error occurred: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CombinedRevenueStatisticsView(RestaurantRevenueStatisticsView):

    def get(self, request, restaurant_id):
        try:
            # Validate restaurant exists
            restaurant = self.get_restaurant(restaurant_id)
            if not restaurant:
                return Response({
                    'error': 'Restaurant not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if user has permission to view this restaurant's data
            if (request.user.role == 'RESTAURANT_USER' and
                    hasattr(request.user, 'restaurants') and
                    request.user.restaurants.id != restaurant.id):
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)

            # Get period parameter
            period = request.query_params.get('period')
            if not period:
                return Response({
                    'error': 'Period parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                start_date, end_date, period_display = self.parse_period(period)
            except ValidationError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get order details for the restaurant in the specified period
            order_details = self.get_order_details(restaurant, start_date, end_date)

            # Calculate food statistics
            food_stats = {}
            category_stats = {}

            for detail in order_details:
                food_id = detail.food.id
                category_id = detail.food.food_category.id

                # Food statistics
                if food_id not in food_stats:
                    food_stats[food_id] = {
                        'food_id': food_id,
                        'food_name': detail.food.name,
                        'category': detail.food.food_category.name,
                        'total_quantity': 0,
                        'total_revenue': 0,
                        'order_count': set()
                    }

                food_stats[food_id]['total_quantity'] += detail.quantity
                food_stats[food_id]['total_revenue'] += detail.sub_total
                food_stats[food_id]['order_count'].add(detail.order.id)

                # Category statistics
                if category_id not in category_stats:
                    category_stats[category_id] = {
                        'category_id': category_id,
                        'category_name': detail.food.food_category.name,
                        'total_quantity': 0,
                        'total_revenue': 0,
                        'food_count': set(),
                        'order_count': set()
                    }

                category_stats[category_id]['total_quantity'] += detail.quantity
                category_stats[category_id]['total_revenue'] += detail.sub_total
                category_stats[category_id]['food_count'].add(detail.food.id)
                category_stats[category_id]['order_count'].add(detail.order.id)

            # Process food statistics
            food_revenue_list = []
            for stats in food_stats.values():
                stats['order_count'] = len(stats['order_count'])
                stats['total_revenue'] = round(stats['total_revenue'], 2)
                food_revenue_list.append(stats)

            food_revenue_list.sort(key=lambda x: x['total_revenue'], reverse=True)

            # Process category statistics
            category_revenue_list = []
            for stats in category_stats.values():
                stats['food_count'] = len(stats['food_count'])
                stats['order_count'] = len(stats['order_count'])
                stats['total_revenue'] = round(stats['total_revenue'], 2)
                category_revenue_list.append(stats)

            category_revenue_list.sort(key=lambda x: x['total_revenue'], reverse=True)

            # Calculate totals
            total_revenue = sum(item['total_revenue'] for item in food_revenue_list)
            total_quantity = sum(item['total_quantity'] for item in food_revenue_list)
            total_orders = len(set(detail.order.id for detail in order_details))

            return Response({
                'success': True,
                'data': {
                    'restaurant_id': restaurant_id,
                    'restaurant_name': restaurant.name,
                    'period': period_display,
                    'period_range': {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    },
                    'summary': {
                        'total_revenue': round(total_revenue, 2),
                        'total_quantity': total_quantity,
                        'total_orders': total_orders,
                        'total_foods': len(food_revenue_list),
                        'total_categories': len(category_revenue_list),
                        'avg_order_value': round(total_revenue / total_orders, 2) if total_orders > 0 else 0
                    },
                    'top_foods': food_revenue_list[:10],  # Top 10 foods
                    'category_revenue': category_revenue_list,
                    'full_food_revenue': food_revenue_list  # All foods if needed
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'An error occurred: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(user=user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """
        Lấy danh sách thông báo cho user hiện tại
        """
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            print(f"Error getting notifications: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        try:
            count = self.get_queryset().filter(is_read=False).count()
            return Response({'unread_count': count})
        except Exception as e:
            print(f"Error getting unread count: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        try:
            queryset = self.get_queryset().filter(is_read=False)
            if queryset.exists():
                queryset.update(is_read=True)
                return Response({'status': 'success'})
            return Response({'status': 'no unread notifications'})
        except Exception as e:
            print(f"Error marking all as read: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """
        Lấy số lượng thông báo chưa đọc của người dùng hiện tại.
        """
        try:
            count = self.get_queryset().filter(is_read=False).count()
            return Response({'unread_count': count})
        except Exception as e:
            print(f"Error getting unread count: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

def send_notification_async(food):
    try:
        notify_new_food(food)
    except Exception as e:
        print(f"Error sending notification: {str(e)}")