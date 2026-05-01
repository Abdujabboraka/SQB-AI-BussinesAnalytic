from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.HomeView.as_view(), name='home'),
    path('analyses/', views.AnalysisListView.as_view(), name='analysis_list'),
    # Analysis creation
    path('analysis/new/', views.AnalysisCreateView.as_view(), name='analysis_create'),
    path('analysis/location-lookup/', views.LocationLookupAPIView.as_view(), name='analysis_location_lookup'),
    path('analysis/ai-health/', views.AIHealthAPIView.as_view(), name='analysis_ai_health'),
    path('analysis/zalog-check/', views.ZalogCheckAPIView.as_view(), name='zalog_check'),
    path('api/notifications/', views.AnalysisNotificationAPIView.as_view(), name='api_notifications'),
    path('api/ai-provider-alert/', views.AIProviderAlertAPIView.as_view(), name='api_ai_provider_alert'),
    path('analysis/<int:pk>/status/', views.AnalysisStatusPageView.as_view(), name='analysis_status_page'),
    path('analysis/<int:pk>/status/api/', views.AnalysisStatusAPIView.as_view(), name='analysis_status_api'),
    path('analysis/notifications/api/', views.AnalysisNotificationsAPIView.as_view(), name='analysis_notifications_api'),
    path('analysis/<int:pk>/delete/', views.AnalysisDeleteView.as_view(), name='analysis_delete'),
    path('analysis/<int:pk>/retry/', views.AnalysisRetryView.as_view(), name='analysis_retry'),
    path('analysis/<int:pk>/edit/', views.AnalysisEditView.as_view(), name='analysis_edit'),
    path('system/switch-ai/<str:provider>/', views.SwitchAIProviderView.as_view(), name='switch_ai_provider'),
    # Admin Statistics
    path('admin-stats/', views.AdminStatsView.as_view(), name='admin_stats'),
    # Auth
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
]
