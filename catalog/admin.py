from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    Country, GeneralStep, Phase, Hurdle, Service, ServiceHurdle, ServicePhase, ServiceTranslation,
    StepTranslation,
)


class ContentFileAdmin(admin.ModelAdmin):
    """Read-only admin for content managed in the data/ files on GitHub (see catalog/content.py)."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def content_path(self, obj):
        raise NotImplementedError

    @admin.display(description=_('Content file'))
    def content_file(self, obj):
        path = self.content_path(obj)
        if not path:
            return '—'
        if settings.CONTENT_REPO_URL:
            return format_html(
                '<a href="{}{}" target="_blank" rel="noopener">{} ↗</a><br>{}',
                settings.CONTENT_REPO_URL, path, _('Edit on GitHub'), f'data/{path}',
            )
        return f'data/{path}'


class ReadOnlyTranslationInline(admin.StackedInline):
    """Translations come from the content files too, so they are shown read-only."""
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class StepTranslationInline(ReadOnlyTranslationInline):
    model = StepTranslation


class ServiceTranslationInline(ReadOnlyTranslationInline):
    model = ServiceTranslation


@admin.register(Country)
class CountryAdmin(ContentFileAdmin):
    list_display = ('code', 'name', 'language')
    readonly_fields = ('content_file',)

    def content_path(self, obj):
        return 'countries.yaml'


@admin.register(GeneralStep)
class GeneralStepAdmin(ContentFileAdmin):
    list_display = ('sort_order', 'title', 'phase', 'topic', 'themes')
    list_filter = ('phase', 'topic', 'themes')
    ordering = ('sort_order',)
    readonly_fields = ('content_file',)
    inlines = [StepTranslationInline]

    def content_path(self, obj):
        return f'steps/{obj.phase.slug}/{obj.source_key}.yaml' if obj.source_key else ''


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ('order', 'name', 'slug')
    readonly_fields = ('name', 'slug', 'order')


class ServicePhaseInline(admin.TabularInline):
    model = ServicePhase
    extra = 1


class ServiceHurdleInline(admin.TabularInline):
    model = ServiceHurdle
    extra = 1


@admin.register(Hurdle)
class HurdleAdmin(admin.ModelAdmin):
    list_display = ('name', 'phase', 'order')
    list_filter = ('phase',)


@admin.register(Service)
class ServiceAdmin(ContentFileAdmin):
    list_display = ('name', 'country', 'general_step', 'is_active')
    list_filter = ('is_active', 'country', 'phases', 'provider')
    search_fields = ('name', 'summary')
    readonly_fields = ('content_file',)
    inlines = [ServiceTranslationInline, ServicePhaseInline, ServiceHurdleInline]

    def content_path(self, obj):
        return f'services/{obj.source_key}.yaml' if obj.source_key else ''
