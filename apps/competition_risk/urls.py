from django.urls import path
from .views import BlockEView

urlpatterns = [
    path('<int:pk>/block-e/', BlockEView.as_view(), name='block-e'),
]
