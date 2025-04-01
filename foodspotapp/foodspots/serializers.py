from rest_framework.serializers import ModelSerializer
from rest_framework.fields import SerializerMethodField
from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview
from rest_framework import serializers

class BaseSerializer(ModelSerializer):
    image = SerializerMethodField()

    def get_image(self, obj):
        if obj.image:  # CloudinaryField tự động tạo URL đầy đủ
            return obj.image.url
        return None

class FoodCategorySerializer(ModelSerializer):
    image = serializers.ImageField(required=False)

    class Meta:
        model = FoodCategory
        fields = ['id', 'name', 'image']

class FoodSerializers(BaseSerializer):
    class Meta:
        model = Food
        fields = ["id", "name", "price", "image"]


class OrderDetailSerializer(BaseSerializer):
    food = FoodSerializers()

    class Meta:
        model = OrderDetail
        fields = ['id', 'food', 'order', 'quantity', 'sub_total']


class OrderSerializer(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    address = serializers.CharField(source='address.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'user_name', 'restaurant', 'restaurant_name', 'ordered_date', 'address', 'total',
                  'delivery_status']

class FoodReviewSerializers(BaseSerializer):
    order_details = OrderDetailSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = FoodReview
        fields = ['id', 'user', 'user_name', 'order_details', 'comment', 'created_date', 'star']

class RestaurantReviewSerializer(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    class Meta:
        model = RestaurantReview
        fields = ['id', 'user', 'user_name', 'restaurant', 'restaurant_name','comment', 'created_date', 'star']