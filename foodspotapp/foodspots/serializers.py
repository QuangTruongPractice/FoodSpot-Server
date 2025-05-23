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
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'required': False},
            'phone_number': {'required': False},
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required")
        return value

    def validate_username(self, value):
        if not value:
            raise serializers.ValidationError("Username is required")
        return value

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
    foods = serializers.SerializerMethodField()
    restaurant = serializers.StringRelatedField()

    class Meta:
        model = Menu
        fields = ['id', 'restaurant', 'name', 'description', 'time_serve', 'foods', 'is_active']

    def get_foods(self, obj):
        time_serve = obj.time_serve
        # Lọc foods theo restaurant và time_serve
        queryset = obj.foods.filter(
            restaurant=obj.restaurant,
            prices__time_serve=time_serve
        ).distinct()

        serializer = FoodInMenuSerializer(queryset, many=True, context={'time_serve': time_serve})
        return serializer.data

class FoodInMenuSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = ['id', 'name', 'image', 'description', 'price']

    def get_price(self, obj):
        # Lấy time_serve từ context truyền vào
        time_serve = self.context.get('time_serve')
        price_obj = obj.prices.filter(time_serve=time_serve).first()
        return price_obj.price if price_obj else None

    def get_image(self, obj):
        return obj.image.url if obj.image else None

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
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    class Meta:
        model = Food
        fields = ["id", "name", "restaurant", "restaurant_name","image", "food_category", "prices", "description"]

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