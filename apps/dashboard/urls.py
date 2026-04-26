from django.urls import path
from .views import DashboardView, PDFExportView

urlpatterns = [
    path('<int:pk>/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('<int:pk>/report/pdf/', PDFExportView.as_view(), name='pdf_export'),
]
