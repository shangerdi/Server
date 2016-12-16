from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^$', views.home, name="home"),
    url(r'^index$', views.IndexView.as_view(), name="index"),
    url(r'^login$', views.LoginView.as_view(), name="login"),
    url(r'^logout$', views.logout, name="logout"),
]