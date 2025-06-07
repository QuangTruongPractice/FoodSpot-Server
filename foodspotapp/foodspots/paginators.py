from rest_framework.pagination import PageNumberPagination

class FoodPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'

class OrderPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = 'page_size'

class ReviewPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'

class NotificationPagination(PageNumberPagination):
    page_size = 10