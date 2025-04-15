from rest_framework.serializers import ModelSerializer
from rest_framework.fields import SerializerMethodField
from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview, FoodPrice
from rest_framework import serializers
from .models import User, Address, Restaurant, SubCart, SubCartItem, Menu

class BaseSerializer(ModelSerializer):
    image = SerializerMethodField()

    def get_image(self, obj):
        if obj.image:  # CloudinaryField tự động tạo URL đầy đủ
            return obj.image.url
        return None

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'role']

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'latitude', 'longitude']

class UserAddressSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'addresses']

class RestaurantSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'phone_number', 'owner', 'star_rating', 'address']

class RestaurantAddressSerializer(serializers.ModelSerializer):
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'address']

class SubCartItemSerializer(serializers.ModelSerializer):
    food = serializers.StringRelatedField()  # Hiển thị tên món ăn
    restaurant = serializers.StringRelatedField()  # Hiển thị tên nhà hàng

    class Meta:
        model = SubCartItem
        fields = ['id', 'food', 'restaurant', 'quantity', 'price']

class SubCartSerializer(serializers.ModelSerializer):
    sub_cart_items = SubCartItemSerializer(many=True, read_only=True)
    restaurant = serializers.StringRelatedField()  # Hiển thị tên nhà hàng

    class Meta:
        model = SubCart
        fields = ['id', 'cart', 'restaurant', 'total_price', 'sub_cart_items']

class MenuSerializer(serializers.ModelSerializer):
    foods = serializers.StringRelatedField(many=True)  # Hiển thị tên các món ăn
    restaurant = serializers.StringRelatedField()  # Hiển thị tên nhà hàng

    class Meta:
        model = Menu
        fields = ['id', 'restaurant', 'name', 'description', 'time_serve', 'foods', 'is_active']

class FoodCategorySerializer(ModelSerializer):
    class Meta:
        model = FoodCategory
        fields = ['id', 'name']

class FoodPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodPrice
        fields = ['time_serve', 'price']

class FoodSerializers(BaseSerializer):
    prices = FoodPriceSerializer(many=True, read_only=True)  # Lấy tất cả giá và thời gian phục vụ

    class Meta:
        model = Food
        fields = ["id", "name", "restaurant", "image", "food_category", "prices", "description"]

class OrderDetailSerializer(BaseSerializer):
    food = serializers.SerializerMethodField()
    class Meta:
        model = OrderDetail
        fields = ['id', 'food', 'order', 'time_serve','quantity', 'sub_total']

    def get_food(self, obj):
        food_data = FoodSerializers(obj.food).data  # Lấy thông tin đầy đủ món ăn
        # Lọc ra chỉ 1 price ứng với time_serve của OrderDetail hiện tại
        matched_price = next(
            (price for price in food_data['prices'] if price['time_serve'] == obj.time_serve),
            None
        )
        food_data['prices'] = [matched_price] if matched_price else []
        return food_data

class OrderSerializer(BaseSerializer):
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all())

    class Meta:
        model = Order
        fields = ['id', 'user', 'restaurant', 'ordered_date', 'address',
                  'total', 'status']
        extra_kwargs = {
            'user': {'read_only': True},
            'ordered_date': {'read_only': True},
        }

class FoodReviewSerializers(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = FoodReview
        fields = ['id', 'user', 'user_name', 'order_detail', 'comment', 'created_date', 'star']

class RestaurantReviewSerializer(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    class Meta:
        model = RestaurantReview
        fields = ['id', 'user', 'user_name', 'restaurant', 'restaurant_name','comment', 'created_date', 'star']


