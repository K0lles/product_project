from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from product_project import settings

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name='schema'),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('admin/', admin.site.urls),
    path('auth/', include('users.urls')),
    path('product/', include('products.urls')),
    path('__debug__/', include('debug_toolbar.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
