from django.urls import path
from rest_framework.authtoken import views

from users.views import SimpleHelloWorld

urlpatterns = [
    path('login/', views.obtain_auth_token, name='api-token-auth'),
    path('retr/', SimpleHelloWorld.as_view(), name='unnecessary')
]
