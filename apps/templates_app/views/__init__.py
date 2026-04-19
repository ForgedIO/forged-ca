from .delete import TemplateDeleteView
from .edit import TemplateCreateView, TemplateEditView
from .index import TemplatesIndexView


__all__ = [
    "TemplatesIndexView",
    "TemplateCreateView",
    "TemplateEditView",
    "TemplateDeleteView",
]
