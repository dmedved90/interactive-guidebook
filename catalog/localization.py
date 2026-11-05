"""Choose the language in which a service's or step's texts are shown.

Texts follow the interface language when a translation in that language exists; every field
the translation leaves empty falls back to English. On service pages the visitor can switch
between English and the service's local language with ``?text=<code>``.
"""
from types import SimpleNamespace

from django.conf import settings
from django.db.models import Prefetch
from django.utils.translation import get_language, get_language_info

from .models import ServiceTranslation, StepTranslation

SERVICE_TEXT_FIELDS = (
    'name', 'summary', 'description', 'stakeholder', 'service_input', 'result', 'remaining_hurdles',
    'duration', 'cost', 'cost_estimate',
)
STEP_TEXT_FIELDS = ('title', 'description', 'objective', 'description_long')
TEXT_PARAM = 'text'


def current_language():
    return (get_language() or settings.LANGUAGE_CODE).split('-')[0]


def _text(obj, fields, translation):
    text = SimpleNamespace(
        language=translation.language if translation else settings.LANGUAGE_CODE,
        is_translated=translation is not None,
        is_draft=translation is not None and not translation.reviewed,
    )
    for name in fields:
        setattr(text, name, (getattr(translation, name) if translation else '') or getattr(obj, name))
    return text


def service_translations(lookup='translations', language=None):
    """Prefetch for services: only the translation in ``language`` (default: the current one)."""
    return Prefetch(
        lookup, queryset=ServiceTranslation.objects.filter(language=language or current_language()),
    )


def step_translations(lookup='translations', language=None):
    """Prefetch for steps: only the translation in ``language`` (default: the current one)."""
    return Prefetch(
        lookup, queryset=StepTranslation.objects.filter(language=language or current_language()),
    )


def _localize(objects, fields, language):
    language = language or current_language()
    for obj in objects:
        translation = next((t for t in obj.translations.all() if t.language == language), None)
        obj.text = _text(obj, fields, translation)
    return objects


def localize_services(services, language=None):
    """Set ``service.text`` on each service. Prefetch with ``service_translations()`` first."""
    return _localize(services, SERVICE_TEXT_FIELDS, language)


def localize_steps(steps, language=None):
    """Set ``step.text`` on each step. Prefetch with ``step_translations()`` first."""
    return _localize(steps, STEP_TEXT_FIELDS, language)


def localize_service_page(service, request):
    """Set ``service.text`` for a service page and return the language switch choices.

    The switch offers English and the country's language when a translation exists; the
    choice comes from ``?text=`` and defaults to the interface language.
    """
    translations = {t.language: t for t in service.translations.all()}
    local = service.country.language if service.country else ''
    available = [settings.LANGUAGE_CODE] + ([local] if local in translations else [])
    requested = request.GET.get(TEXT_PARAM, '')
    language = requested if requested in available else current_language()
    service.text = _text(service, SERVICE_TEXT_FIELDS, translations.get(language))
    if len(available) < 2:
        return []
    return [
        {
            'code': code,
            'name': get_language_info(code)['name_local'],
            'query': f'?{TEXT_PARAM}={code}',
            'active': code == service.text.language,
        }
        for code in available
    ]
