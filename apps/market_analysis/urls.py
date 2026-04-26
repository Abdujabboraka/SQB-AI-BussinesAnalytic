from django.urls import path
from .views import BlockAView

urlpatterns = [
    path('<int:pk>/block-a/', BlockAView.as_view(), name='block-a'),
]
