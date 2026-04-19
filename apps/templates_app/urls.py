from django.urls import path

from .views import (
    TemplateCreateView,
    TemplateDeleteView,
    TemplateEditView,
    TemplatesIndexView,
)


app_name = "templates_app"


urlpatterns = [
    path("",                    TemplatesIndexView.as_view(),  name="index"),
    path("new/",                TemplateCreateView.as_view(),  name="new"),
    path("<int:pk>/edit/",      TemplateEditView.as_view(),    name="edit"),
    path("<int:pk>/delete/",    TemplateDeleteView.as_view(),  name="delete"),
]
