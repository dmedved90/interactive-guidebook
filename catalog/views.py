from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import ListView, DetailView, TemplateView, View

from .localization import (
    current_language, localize_service_page, localize_services, localize_steps, service_translations,
    step_translations,
)
from .models import THEMES, Country, Phase, Service

ALL_COUNTRIES = 'all'


class CountrySelectionMixin:
    """Resolve the country the visitor wants to see services for.

    ``?country=<code>`` selects a country and ``?country=all`` shows every
    country. Without the parameter, logged-in managers see their own country
    and anonymous visitors see all countries.
    """

    def get_selected_country(self):
        if not hasattr(self, '_selected_country'):
            code = self.request.GET.get('country', '').strip()
            country = None
            if code and code.lower() != ALL_COUNTRIES:
                country = Country.objects.filter(code__iexact=code).first()
            elif not code:
                country = getattr(self.request.user, 'country', None)
            self._selected_country = country
        return self._selected_country

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        country = self.get_selected_country()
        ctx['countries'] = Country.objects.all()
        ctx['country'] = country
        ctx['country_param'] = country.code if country else ALL_COUNTRIES
        return ctx


class ServiceListView(CountrySelectionMixin, ListView):
    """Public service catalog with phase, country and keyword filters."""

    model = Service
    template_name = 'catalog/service_list.html'
    context_object_name = 'services'
    paginate_by = 24

    def get_queryset(self):
        qs = (
            Service.objects.filter(is_active=True)
            .select_related('country')
            .prefetch_related('servicephase_set__phase', service_translations())
            .order_by('pk')  # stable order for pagination; keeps import order
        )
        country = self.get_selected_country()
        if country:
            qs = qs.filter(country=country)
        phase_slug = self.request.GET.get('phase', '').strip()
        q = self.request.GET.get('q', '').strip()
        if phase_slug:
            qs = qs.filter(phases__slug=phase_slug)
        if q:
            # Search English and the texts in the visitor's language.
            lang = current_language()
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(summary__icontains=q) |
                Q(description__icontains=q) |
                Q(translations__language=lang, translations__name__icontains=q) |
                Q(translations__language=lang, translations__summary__icontains=q) |
                Q(translations__language=lang, translations__description__icontains=q)
            ).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        localize_services(ctx['services'])
        ctx['phases'] = Phase.objects.all()
        ctx['active_phase'] = self.request.GET.get('phase', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class ServiceDetailView(DetailView):
    """Public service page. Deactivated services are hidden."""
    queryset = Service.objects.filter(is_active=True).select_related('country').prefetch_related('translations')
    template_name = 'catalog/service_detail.html'
    context_object_name = 'service'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['text_languages'] = localize_service_page(self.object, self.request)
        ctx['service_phases'] = self.object.servicephase_set.select_related('phase')
        ctx['service_hurdles'] = self.object.servicehurdle_set.select_related('hurdle__phase')
        return ctx


class GuidebookView(CountrySelectionMixin, TemplateView):
    """Public Interactive Guidebook: general steps with country-specific services."""
    template_name = 'catalog/guidebook.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        country = self.get_selected_country()

        services = (
            Service.objects.filter(is_active=True, general_step__isnull=False)
            .select_related('country')
            .prefetch_related(service_translations())
        )
        if country:
            services = services.filter(country=country)
        services_by_step = defaultdict(list)
        for service in localize_services(services.order_by('pk')):
            services_by_step[service.general_step_id].append(service)

        # ?theme=<key> shows only the steps of that theme (e.g. building a solar power plant).
        theme = self.request.GET.get('theme', '').strip()
        if theme not in THEMES:
            theme = ''

        phase_data = []
        has_draft = any(s.text.is_draft for step in services_by_step.values() for s in step)
        total_steps = shown_steps = 0
        for phase in Phase.objects.prefetch_related('general_steps', step_translations('general_steps__translations')):
            all_steps = list(phase.general_steps.all())
            total_steps += len(all_steps)
            steps = [
                {'step': step, 'services': services_by_step[step.pk]}
                for step in localize_steps(all_steps)
                if not theme or theme in step.theme_list
            ]
            shown_steps += len(steps)
            has_draft = has_draft or any(entry['step'].text.is_draft for entry in steps)
            if steps or not theme:
                phase_data.append({'phase': phase, 'steps': steps})

        ctx['phase_data'] = phase_data
        ctx['themes'] = THEMES.items()
        ctx['active_theme'] = theme
        ctx['active_theme_label'] = THEMES.get(theme, '')
        ctx['shown_steps'] = shown_steps
        ctx['total_steps'] = total_steps
        ctx['has_draft_translation'] = has_draft
        user = self.request.user
        ctx['can_save_default'] = (
            user.is_authenticated and country is not None and user.country_id != country.pk
        )
        return ctx


class SetCountryView(LoginRequiredMixin, View):
    """Save a country as the logged-in user's default and return to the guidebook."""

    def post(self, request):
        country_code = request.POST.get('country_code', '').strip()
        country = Country.objects.filter(code__iexact=country_code).first() if country_code else None
        if country:
            request.user.country = country
            request.user.save(update_fields=['country'])
            messages.success(request, _('%(country)s is now your default country.') % {'country': country.name})
        return redirect(reverse('catalog:guidebook'))
