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


# class ChatRoomPagination(PageNumberPagination):
#     page_size = 10
#     page_size_query_param = 'page_size'
#     max_page_size = 100
#
# class MessagePagination(PageNumberPagination):
#     page_size = 20
#     page_size_query_param = 'page_size'
#     max_page_size = 100

class NotificationPagination(PageNumberPagination):
    page_size = 10