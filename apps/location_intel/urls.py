from django.urls import path
from .views import BlockCView

urlpatterns = [
    path('<int:pk>/block-c/', BlockCView.as_view(), name='block-c'),
]
