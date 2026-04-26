from django.urls import path
from .views import BlockBView

urlpatterns = [
    path('<int:pk>/block-b/', BlockBView.as_view(), name='block-b'),
]
