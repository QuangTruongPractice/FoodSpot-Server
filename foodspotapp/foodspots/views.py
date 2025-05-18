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
    User, Address, Menu
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
    permission_classes = [permissions.IsAuthenticated, IsOrderOwner]
    pagination_class = OrderPagination

    def get_object(self):
        return get_object_or_404(Order, pk=self.kwargs.get('pk'))

    def get_queryset(self, request):
        user = request.user
        if user.role == 'RESTAURANT_USER':
            return Order.objects.filter(restaurant__owner=user).order_by('-ordered_date', '-id')
        return Order.objects.filter(user=user).order_by('-ordered_date', '-id')

    def list(self, request, *args, **kwargs):
        orders = self.get_queryset(request)

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

        # Serialize và trả về chi tiết đơn hàng
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
        order.save()  # Lưu lại đối tượng order đã cập nhật
        return Response(OrderSerializer(order).data)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()

        # Kiểm tra quyền xóa đơn hàng
        if order.user != request.user and order.restaurant.owner != request.user:
            return Response({"detail": "Bạn không có quyền xóa đơn hàng này."}, status=status.HTTP_403_FORBIDDEN)

        # Xóa đơn hàng
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['post'], detail=False, url_path='checkout')
    def checkout(self, request):
        """
        Xử lý quy trình đặt hàng hoàn chỉnh (gồm Order + Payment + OrderDetail).
        Dành cho cả COD và MoMo.
        """
        # Lấy dữ liệu từ request.data
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


class OrderDetailViewSet(viewsets.ModelViewSet):
    queryset = OrderDetail.objects.select_related(
        'food'
    )
    serializer_class = OrderDetailSerializer


class FoodPriceViewSet(viewsets.ModelViewSet):
    queryset = FoodPrice.objects.select_related('food')
    serializer_class = FoodPriceSerializer

    def partial_update(self, request, *args, **kwargs):
        """Cập nhật chỉ trường price."""
        if set(request.data.keys()) != {"price"}:
            raise ValidationError({"detail": "Chỉ được phép cập nhật trường 'price'."})

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class FoodViewSet(viewsets.ViewSet, generics.ListAPIView, generics.RetrieveAPIView):
    serializer_class = FoodSerializers
    pagination_class = FoodPagination

    def get_permissions(self):
        # Kiểm tra các action (hành động) cần quyền RestaurantOwner (thêm, chỉnh sửa, xóa)
        if self.action in ['create', 'update', 'destroy']:
            return [IsAuthenticated(), IsRestaurantOwner()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = Food.objects.prefetch_related('menus__restaurant').all()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(menus__restaurant__name__icontains=search)
            ).distinct()

        # Lọc theo tên món ăn
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)

        # Lọc theo giá
        price_min = self.request.query_params.get('price_min')
        price_max = self.request.query_params.get('price_max')

        if price_min or price_max:
            # Lọc theo giá trong bảng FoodPrice
            food_prices = FoodPrice.objects.all()

            if price_min:
                food_prices = food_prices.filter(price__gte=price_min)

            if price_max:
                food_prices = food_prices.filter(price__lte=price_max)

            # Lọc các món ăn có giá thỏa mãn
            queryset = queryset.filter(id__in=food_prices.values('food_id')).distinct()

        # Lọc theo danh mục
        food_category = self.request.query_params.get('food_category')
        if food_category:
            queryset = queryset.filter(food_category__name__icontains=food_category)

        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(food_category_id=category_id)

        restaurant_id = self.request.query_params.get('restaurant_id')
        if restaurant_id:
            queryset = queryset.filter(menus__restaurant_id=restaurant_id)

        # Lọc theo tên nhà hàng
        restaurant_name = self.request.query_params.get('restaurant_name')
        if restaurant_name:
            queryset = queryset.filter(menus__restaurant__name__icontains=restaurant_name)

        return queryset

    def create(self, request):
        serializer = FoodSerializers(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        food = self.get_object(pk)
        serializer = FoodSerializers(food, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        food = self.get_object(pk)
        food.delete()
        return Response({"message": "Món ăn đã bị xóa thành công."}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Lấy tất cả reviews của một món ăn."""
        try:
            food = Food.objects.get(pk=pk)
            food_reviews = FoodReview.objects.filter(order_detail__food=food, parent=None)  # chỉ lấy review chính
            serializer = FoodReviewSerializers(food_reviews, many=True)
            return Response(serializer.data)
        except Food.DoesNotExist:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)

class FoodCategoryViewSet(viewsets.ModelViewSet):
    queryset = FoodCategory.objects.all()
    serializer_class = FoodCategorySerializer

    def get_permissions(self):
        if self.action == 'list':  # Chỉ phương thức list mới được phép cho phép mọi người
            return [permissions.AllowAny()]
        # Các phương thức khác chỉ cho phép Admin
        return [permissions.IsAuthenticated(), IsAdminUser()]  # Admin mới có thể thao tác POST, PATCH, DELETE

    def partial_update(self, request, *args, **kwargs):
        """Cập nhật một food category, chỉ cho phép cập nhật tên."""
        instance = self.get_object()

        # Chỉ cho phép cập nhật tên (name), không cho phép thay đổi các trường khác
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

        allowed_fields = {'comment', 'star'}
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
        if self.action == 'register':
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

        if not (user.is_superuser or user.role == 'ADMIN' or user == target_user):
            return Response({"error": "You can only view your own details."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(target_user)
        return Response(serializer.data)

    def create(self, request):
        user = request.user
        if not (user.is_superuser or user.role == 'ADMIN'):
            return Response({"error": "Only superusers or admins can create new users."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

    @action(methods=['post'], detail=False, url_path='register')
    def register(self, request):
        """Đăng ký người dùng mới (không yêu cầu đăng nhập)."""
        print("Dữ liệu nhận được:", request.data)

        # Kiểm tra các trường bắt buộc
        required_fields = ['email', 'password']
        if request.data.get('role') == 'RESTAURANT_USER':
            required_fields.append('restaurant_name')

        for field in required_fields:
            if not request.data.get(field):
                return Response(
                    {"error": f"Trường {field} là bắt buộc."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Sử dụng serializer để validate dữ liệu
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Lấy dữ liệu đã validate
            user_data = serializer.validated_data
            role = user_data.get('role', 'CUSTOMER')  # Mặc định là CUSTOMER
            if role not in ['CUSTOMER', 'RESTAURANT_USER']:
                return Response({"error": "Vai trò không hợp lệ. Chỉ chấp nhận CUSTOMER hoặc RESTAURANT_USER."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Kiểm tra email đã tồn tại
            email = user_data['email']
            if User.objects.filter(email=email).exists():
                print(f"Email {email} đã tồn tại.")
                return Response({"error": "Email đã được sử dụng."}, status=status.HTTP_400_BAD_REQUEST)

            # Tạo username duy nhất từ email
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user_data['username'] = username

            # Đặt is_approved dựa trên role
            user_data['is_approved'] = (role != 'RESTAURANT_USER')

            # Lưu password
            password = request.data.get('password')
            user_data.pop('password', None)  # Loại bỏ password khỏi user_data

            # Tạo user
            user = User(**user_data)
            user.set_password(password)
            user.save()

            # Nếu là RESTAURANT_USER, tạo Restaurant
            response_message = "Đăng ký thành công!"
            if role == 'RESTAURANT_USER':
                restaurant_name = request.data.get('restaurant_name').strip()
                if len(restaurant_name) < 3:
                    user.delete()
                    return Response({"error": "Tên nhà hàng phải có ít nhất 3 ký tự."},
                                    status=status.HTTP_400_BAD_REQUEST)
                Restaurant.objects.create(name=restaurant_name, owner=user, is_approved=False)
                response_message = "Tài khoản nhà hàng đã được tạo. Vui lòng chờ Admin phê duyệt."

            response_data = UserSerializer(user).data
            response_data['message'] = response_message
            print("Đăng ký thành công:", response_data)

            return Response(response_data, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
            error_message = str(e).lower()
            print(f"IntegrityError occurred: {error_message}")
            return Response({"error": "Email hoặc username đã tồn tại."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return Response({"error": f"Đã xảy ra lỗi không mong muốn: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

class UserAddressViewSet(viewsets.ViewSet):
    def get_permissions(self):
        """Yêu cầu xác thực cho tất cả các hành động."""
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
        """Lấy chi tiết một địa chỉ cụ thể (chỉ ADMIN hoặc chủ sở hữu)."""
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
        """Tạo một địa chỉ mới cho người dùng đã xác thực."""
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
        """Cập nhật một địa chỉ hiện có (chỉ ADMIN hoặc chủ sở hữu)."""
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
        """Xóa một địa chỉ (chỉ ADMIN hoặc chủ sở hữu)."""
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
        # Kiểm tra các action (hành động) cần quyền RestaurantOwner (thêm, chỉnh sửa, xóa)
        if self.action in ['create', 'update', 'destroy']:
            return [IsAuthenticated(), RestaurantOwner()]
        # Các action còn lại (list, retrieve) công khai
        return [AllowAny()]

    def list(self, request):
        """Lấy danh sách nhà hàng (công khai)."""
        queryset = Restaurant.objects.all()
        serializer = RestaurantSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Lấy chi tiết một nhà hàng (công khai)."""
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            serializer = RestaurantSerializer(restaurant)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        """Tạo nhà hàng mới (chỉ RESTAURANT_USER)."""
        user = request.user
        if user.role != 'RESTAURANT_USER':
            return Response({"error": "Only restaurant users can create a restaurant."}, status=status.HTTP_403_FORBIDDEN)

        serializer = RestaurantSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner=user)  # Gán người tạo là owner
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """Cập nhật nhà hàng (chỉ RESTAURANT_USER và là owner)."""
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
        """Cập nhật một phần nhà hàng (chỉ RESTAURANT_USER và là owner)."""
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
        """Xóa nhà hàng (chỉ RESTAURANT_USER và là owner)."""
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            self.check_object_permissions(request, restaurant)  # Kiểm tra quyền
            restaurant.delete()
            return Response({"message": "Restaurant deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def menus(self, request, pk=None):
        """Lấy tất cả menus của nhà hàng."""
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            menus = Menu.objects.filter(restaurant=restaurant)  # Lọc các menu của nhà hàng
            serializer = MenuSerializer(menus, many=True)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def foods(self, request, pk=None):
        """Lấy tất cả món ăn của nhà hàng."""
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            foods = Food.objects.filter(restaurant=restaurant)  # Lọc các món ăn của nhà hàng
            serializer = FoodSerializers(foods, many=True)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Lấy tất cả restaurant reviews của nhà hàng."""
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            restaurant_reviews = RestaurantReview.objects.filter(restaurant=restaurant)
            serializer = RestaurantReviewSerializer(restaurant_reviews, many=True)
            return Response(serializer.data)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)


class RestaurantAddressViewSet(viewsets.ViewSet):
    def get_permissions(self):
        # Công khai để xem danh sách và chi tiết
        return [AllowAny()]

    def list(self, request):
        """Lấy danh sách nhà hàng với địa chỉ (công khai)."""
        queryset = Restaurant.objects.all()
        serializer = RestaurantAddressSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Lấy chi tiết nhà hàng với địa chỉ (công khai)."""
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
        """Lấy danh sách SubCart của người dùng hiện tại (chỉ CUSTOMER)."""
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can view their sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        queryset = SubCart.objects.filter(cart__user=user)
        serializer = SubCartSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Lấy chi tiết một SubCart (chỉ CUSTOMER và là của họ)."""
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
        """Tạo SubCart mới (chỉ CUSTOMER)."""
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can create sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SubCartSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """Xóa SubCart (chỉ CUSTOMER và là của họ)."""
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
        """Lấy danh sách SubCartItem của người dùng hiện tại (chỉ CUSTOMER)."""
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can view their sub-cart items."}, status=status.HTTP_403_FORBIDDEN)

        queryset = SubCartItem.objects.filter(sub_cart__cart__user=user)
        serializer = SubCartItemSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Lấy chi tiết một SubCartItem (chỉ CUSTOMER và là của họ)."""
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
        """Tạo SubCartItem mới (chỉ CUSTOMER)."""
        user = request.user
        if user.role != 'CUSTOMER':
            return Response({"error": "Only customers can add items to their sub-carts."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SubCartItemSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """Cập nhật SubCartItem (chỉ CUSTOMER và là của họ, ví dụ: cập nhật số lượng)."""
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
        """Xóa SubCartItem (chỉ CUSTOMER và là của họ)."""
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
        # Công khai để xem, yêu cầu đăng nhập và quyền để tạo, chỉnh sửa, xóa
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def list(self, request):
        """Lấy danh sách menu (công khai)."""
        queryset = Menu.objects.all()
        serializer = MenuSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Lấy chi tiết một menu (công khai)."""
        try:
            menu = Menu.objects.get(pk=pk)
            serializer = MenuSerializer(menu)
            return Response(serializer.data)
        except Menu.DoesNotExist:
            return Response({"error": "Menu not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        """Tạo menu mới (chỉ RESTAURANT_USER và cho nhà hàng của họ)."""
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
        """Cập nhật menu (chỉ RESTAURANT_USER và cho nhà hàng của họ)."""
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
        """Xóa menu (chỉ RESTAURANT_USER và cho nhà hàng của họ)."""
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
