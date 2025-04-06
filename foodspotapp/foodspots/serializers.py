from rest_framework.serializers import ModelSerializer
from rest_framework.fields import SerializerMethodField
from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview, Payment, Restaurant, Address
from rest_framework import serializers

class BaseSerializer(ModelSerializer):
    image = SerializerMethodField()

    def get_image(self, obj):
        if obj.image:  # CloudinaryField tự động tạo URL đầy đủ
            return obj.image.url
        return None

class FoodCategorySerializer(ModelSerializer):
    class Meta:
        model = FoodCategory
        fields = ['id', 'name']

class FoodSerializers(BaseSerializer):
    food_category_name = serializers.CharField(source='food_category.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    class Meta:
        model = Food
        fields = ["id", "name", "price", "image", "food_category",
                  "food_category_name", "description", "star_rating", "restaurant_name"]

class FoodDetailSerializers(serializers.ModelSerializer):
    food_category_name = serializers.CharField(source='food_category.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    menus = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = ["id", "name", "price", "image", "food_category",
                  "food_category_name", "description", "star_rating",
                            "restaurant_name", "menus"]

    def get_menus(self, obj):
        menu_list = []
        menus = obj.menus.select_related('restaurant').all()

        for menu in menus:
            menu_list.append({
                "menu_name": menu.name,
                "is_available": obj.is_available,
                "time_serve": obj.time_serve,
            })

        return menu_list


class OrderDetailSerializer(BaseSerializer):
    food = FoodSerializers()
    class Meta:
        model = OrderDetail
        fields = ['id', 'food', 'order', 'quantity', 'sub_total']


class OrderSerializer(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all())
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    order_status = serializers.CharField(source='status', read_only=True)
    payment_method = serializers.CharField(source='payments.payment_method', read_only=True)
    payment_status = serializers.CharField(source='payments.status', read_only=True)


    class Meta:
        model = Order
        fields = ['id', 'user', 'user_name', 'restaurant', 'restaurant_name', 'ordered_date', 'address',
                  'total', 'order_status', 'payment_method', 'payment_status']
        extra_kwargs = {'user': {'read_only': True}}


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