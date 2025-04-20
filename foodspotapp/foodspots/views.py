from allauth.headless.base.views import APIView
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action, api_view
from .perms import IsAdminUser, IsOrderOwner, IsOwnerOrAdmin, IsRestaurantOwner
from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview, Restaurant, FoodPrice
from .serializers import (OrderSerializer, OrderDetailSerializer, FoodSerializers,
                          FoodCategorySerializer, FoodReviewSerializers, RestaurantReviewSerializer, FoodPriceSerializer)


def index(request):
    return HttpResponse("foodspots")


class OrderViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOrderOwner]

    def get_object(self):
        """
        Lấy đối tượng Order từ pk trong URL, nếu không có thì trả về lỗi 404.
        """
        return get_object_or_404(Order, pk=self.kwargs.get('pk'))

    def list(self, request, *args, **kwargs):
        user = self.request.user
        # Lọc đơn hàng theo vai trò người dùng
        orders = Order.objects.filter(
            restaurant__owner=user) if user.role == 'RESTAURANT_USER' else Order.objects.filter(user=user)
        return Response(OrderSerializer(orders, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        """
        Truyền chi tiết đơn hàng, bao gồm cả order_details.
        """
        order = self.get_object()

        class OrderDetailWithItemsSerializer(OrderSerializer):
            order_details = OrderDetailSerializer(many=True, read_only=True)

            class Meta(OrderSerializer.Meta):
                fields = OrderSerializer.Meta.fields + ['order_details']

        # Serialize và trả về chi tiết đơn hàng
        return Response(OrderDetailWithItemsSerializer(order).data)

    def create(self, request, *args, **kwargs):
        """
        Tạo đơn hàng mới và gán người dùng hiện tại vào đơn hàng.
        """
        order_serializer = OrderSerializer(data=request.data)
        if order_serializer.is_valid():
            order_serializer.save(user=request.user)
            return Response(order_serializer.data, status=status.HTTP_201_CREATED)
        return Response(order_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        """
        Cập nhật trạng thái đơn hàng.
        """
        order = self.get_object()
        status = request.data.get('status')

        if not status:
            return Response({"error": "Chỉ được cập nhật trạng thái đơn hàng."}, status=status.HTTP_400_BAD_REQUEST)

        order.status = status
        order.save()  # Lưu lại đối tượng order đã cập nhật
        return Response(OrderSerializer(order).data)

    def destroy(self, request, *args, **kwargs):
        """
        Xóa đơn hàng nếu người dùng có quyền xóa, chỉ khi đơn hàng thuộc về người dùng hiện tại hoặc chủ nhà hàng.
        """
        order = self.get_object()

        # Kiểm tra quyền xóa đơn hàng
        if order.user != request.user and order.restaurant.owner != request.user:
            return Response({"detail": "Bạn không có quyền xóa đơn hàng này."}, status=status.HTTP_403_FORBIDDEN)

        # Xóa đơn hàng
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
    # Phân quyền cho các phương thức
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsRestaurantOwner]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Food.objects.prefetch_related('menus__restaurant').all()

        # Lọc theo tên món ăn
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)

        # Lọc theo giá
        price_min = self.request.query_params.get('price_min')
        if price_min:
            queryset = queryset.filter(price__gte=price_min)

        price_max = self.request.query_params.get('price_max')
        if price_max:
            queryset = queryset.filter(price__lte=price_max)

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


# foodspots/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import User, Address, Restaurant, SubCart, SubCartItem, Menu
from .serializers import (
    UserSerializer, UserAddressSerializer, RestaurantSerializer,
    RestaurantAddressSerializer, SubCartSerializer, SubCartItemSerializer,
    MenuSerializer
)
from .perms import RestaurantOwner

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from .models import User
from .serializers import UserSerializer

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import User
from .serializers import UserSerializer
from django.db import IntegrityError

class UserViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action == 'register':
            return []
        return [IsAuthenticated()]

    def list(self, request):
        user = request.user
        if user.role != 'ADMIN':
            return Response({"error": "Only admins can view the user list."}, status=status.HTTP_403_FORBIDDEN)

        queryset = User.objects.all()
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if user.role != 'ADMIN' and user != target_user:
            return Response({"error": "You can only view your own details."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(target_user)
        return Response(serializer.data)

    def create(self, request):
        user = request.user
        if user.role != 'ADMIN':
            return Response({"error": "Only admins can create new users."}, status=status.HTTP_403_FORBIDDEN)

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
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserSerializer(user).data)

    @action(methods=['post'], detail=False, url_path='register')
    def register(self, request):
        """Đăng ký người dùng mới (không yêu cầu đăng nhập)."""
        print("Dữ liệu nhận được:", request.data)

        # Kiểm tra dữ liệu đầu vào
        if 'username' not in request.data or not request.data['username']:
            return Response({"error": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)

        if 'password' not in request.data or not request.data['password']:
            return Response({"error": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        if 'email' not in request.data or not request.data['email']:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Kiểm tra username và email có tồn tại trước không
        username = request.data['username']
        email = request.data['email']
        if User.objects.filter(username=username).exists():
            print(f"Username {username} already exists in the database.")
            return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email=email).exists():
            print(f"Email {email} already exists in the database.")
            return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)

        # Sử dụng serializer để kiểm tra dữ liệu
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user_data = serializer.validated_data
                user_data['role'] = 'CUSTOMER'
                user = User(**user_data)
                user.set_password(request.data['password'])
                user.save()
                response_data = UserSerializer(user).data
                print("Đăng ký thành công:", response_data)
                return Response(response_data, status=status.HTTP_201_CREATED)
            except IntegrityError as e:
                error_message = str(e).lower()
                print(f"IntegrityError occurred: {error_message}")
                if 'username' in error_message:
                    return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
                if 'email' in error_message:
                    return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": f"An error occurred while saving the user: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserAddressViewSet(viewsets.ViewSet):
    def get_permissions(self):
        # Hạn chế truy cập: chỉ ADMIN hoặc chính người dùng đó
        return [IsAuthenticated()]

    def list(self, request):
        """Lấy danh sách người dùng với địa chỉ (chỉ dành cho ADMIN)."""
        user = request.user
        if user.role != 'ADMIN':
            return Response({"error": "Only admins can view the user address list."}, status=status.HTTP_403_FORBIDDEN)

        queryset = User.objects.all()
        serializer = UserAddressSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Lấy chi tiết người dùng với địa chỉ (chỉ ADMIN hoặc chính người dùng đó)."""
        user = request.user
        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if user.role != 'ADMIN' and user != target_user:
            return Response({"error": "You can only view your own address details."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserAddressSerializer(target_user)
        return Response(serializer.data)

class RestaurantViewSet(viewsets.ViewSet):
    def get_permissions(self):
        # Công khai để xem danh sách và chi tiết
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        # Yêu cầu đăng nhập và quyền RestaurantOwner để tạo, chỉnh sửa
        return [IsAuthenticated(), RestaurantOwner()]

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

    def destroy(self, request, pk=None):
        """Xóa nhà hàng (chỉ RESTAURANT_USER và là owner)."""
        try:
            restaurant = Restaurant.objects.get(pk=pk)
            self.check_object_permissions(request, restaurant)  # Kiểm tra quyền
            restaurant.delete()
            return Response({"message": "Restaurant deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
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

class SubCartViewSet(viewsets.ViewSet):
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
            sub_cart.delete()
            return Response({"message": "SubCart deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except SubCart.DoesNotExist:
            return Response({"error": "SubCart not found"}, status=status.HTTP_404_NOT_FOUND)

class SubCartItemViewSet(viewsets.ViewSet):
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
            sub_cart_item.delete()
            return Response({"message": "SubCartItem deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except SubCartItem.DoesNotExist:
            return Response({"error": "SubCartItem not found"}, status=status.HTTP_404_NOT_FOUND)

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