from django.urls import path

from .views import FinishView, StepLifetimesView, StepReviewView, StepRoleView


app_name = "wizard"


urlpatterns = [
    path("", StepRoleView.as_view(), name="step_role"),
    path("lifetimes/", StepLifetimesView.as_view(), name="step_lifetimes"),
    path("review/", StepReviewView.as_view(), name="step_review"),
    path("finish/", FinishView.as_view(), name="finish"),
]
