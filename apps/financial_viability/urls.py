from django.urls import path
from .views import BlockDView

urlpatterns = [
    path('<int:pk>/block-d/', BlockDView.as_view(), name='block-d'),
]
