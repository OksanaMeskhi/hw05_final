# yatube/urls.py
from django.contrib import admin
# импорт include позволит использовать адреса, включенные в приложения
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # импорт правил из приложения posts
    path('', include('posts.urls', namespace='index')),
    path('admin/', admin.site.urls),
    path('auth/', include('users.urls')),
    path('auth/', include('django.contrib.auth.urls')),
    path('about/', include('about.urls', namespace='about')),
]

handler404 = 'core.views.page_not_found'
handler403 = 'core.views.permission_denied'

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
