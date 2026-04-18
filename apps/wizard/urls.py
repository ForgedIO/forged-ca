from django.urls import path

from . import views

app_name = "wizard"

urlpatterns = [
    path("", views.step_role, name="step_role"),
    path("lifetimes/", views.step_lifetimes, name="step_lifetimes"),
    path("review/", views.step_review, name="step_review"),
    path("finish/", views.finish, name="finish"),
]
