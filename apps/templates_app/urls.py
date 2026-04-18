from django.urls import path

from .views import TemplatesIndexView


app_name = "templates_app"


urlpatterns = [
    path("", TemplatesIndexView.as_view(), name="index"),
]
