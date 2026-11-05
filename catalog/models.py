from django.db import models
from django.utils.translation import gettext_lazy as _


# The phases are fixed (migration 0002); their names are shown in the interface language.
PHASE_LABELS = {
    'planning': _('Planning'),
    'realisation': _('Realisation'),
    'operation': _('Operation'),
}


class Phase(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField()
    order = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return str(self.label)

    @property
    def label(self):
        """The phase name in the current interface language."""
        return PHASE_LABELS.get(self.slug, self.name)


class Country(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    # Language of the country's services besides English (an interface language code).
    language = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('country')
        verbose_name_plural = _('countries')

    def __str__(self):
        return self.name


# Thematic filters of the guidebook: steps list the themes they belong to (``themes:`` in YAML).
THEMES = {
    'solar': _('Building a solar power plant'),
}

# Who delivers a service: the one-stop shop (energy agency) itself or an external provider.
PROVIDER_CHOICES = [
    ('oss', _('One-stop shop')),
    ('external', _('External provider')),
]


class GeneralStep(models.Model):
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    description_long = models.TextField(blank=True)
    objective    = models.TextField(blank=True)
    phase        = models.ForeignKey(Phase, on_delete=models.PROTECT, related_name='general_steps')
    topic        = models.CharField(max_length=50, blank=True)  # Social / PV Plant / REC
    # Comma-separated theme keys (THEMES) for the guidebook's thematic filter.
    themes       = models.CharField(max_length=200, blank=True)
    sort_order   = models.PositiveIntegerField(default=0)
    # File name in data/steps/<phase>/ that this step comes from (see catalog/content.py).
    source_key   = models.CharField(max_length=100, unique=True, null=True, blank=True, editable=False)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return self.title

    @property
    def theme_list(self):
        return [t for t in self.themes.split(',') if t]


class Hurdle(models.Model):
    phase = models.ForeignKey(Phase, on_delete=models.PROTECT, related_name='hurdles')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['phase__order', 'order']

    def __str__(self):
        return self.name


class Service(models.Model):
    name         = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=150, unique=True)
    summary      = models.CharField(max_length=500)
    description  = models.TextField(blank=True)
    phases       = models.ManyToManyField(Phase, through='ServicePhase', related_name='services')
    hurdles      = models.ManyToManyField(Hurdle, through='ServiceHurdle', related_name='services')
    is_active    = models.BooleanField(default=True)

    # Country-specific fields
    country      = models.ForeignKey(
        Country, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='services'
    )
    general_step = models.ForeignKey(
        GeneralStep, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='services'
    )
    web_link        = models.TextField(blank=True)
    stakeholder     = models.CharField(max_length=300, blank=True)
    service_input   = models.TextField(blank=True)
    result          = models.TextField(blank=True)
    remaining_hurdles = models.TextField(blank=True)
    duration        = models.CharField(max_length=100, blank=True)
    cost            = models.CharField(max_length=200, blank=True)
    cost_estimate   = models.CharField(max_length=200, blank=True)
    provider        = models.CharField(max_length=20, choices=PROVIDER_CHOICES, blank=True)
    # "<country>/<file name>" in data/services/ that this service comes from.
    source_key   = models.CharField(max_length=110, unique=True, null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def official_link(self):
        """The web link, only if it is an http(s) URL (safe to use as href)."""
        link = (self.web_link or '').strip()
        return link if link.startswith(('https://', 'http://')) else ''


class ServiceTranslation(models.Model):
    """A service's texts in the country's language; empty fields fall back to English."""
    service  = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10)
    name     = models.CharField(max_length=200, blank=True)
    summary  = models.CharField(max_length=500, blank=True)
    description   = models.TextField(blank=True)
    stakeholder   = models.CharField(max_length=300, blank=True)
    service_input = models.TextField(blank=True)
    result        = models.TextField(blank=True)
    remaining_hurdles = models.TextField(blank=True)
    duration      = models.CharField(max_length=100, blank=True)
    cost          = models.CharField(max_length=200, blank=True)
    cost_estimate = models.CharField(max_length=200, blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('translation')
        verbose_name_plural = _('translations')
        constraints = [
            models.UniqueConstraint(fields=['service', 'language'], name='unique_service_translation')
        ]

    def __str__(self):
        return self.language


class StepTranslation(models.Model):
    """A guidebook step's texts in one interface language; empty fields fall back to English."""
    step     = models.ForeignKey(GeneralStep, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10)
    title    = models.CharField(max_length=200, blank=True)
    description      = models.TextField(blank=True)
    objective        = models.TextField(blank=True)
    description_long = models.TextField(blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('translation')
        verbose_name_plural = _('translations')
        constraints = [
            models.UniqueConstraint(fields=['step', 'language'], name='unique_step_translation')
        ]

    def __str__(self):
        return self.language


class ServicePhase(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    phase   = models.ForeignKey(Phase, on_delete=models.CASCADE)
    notes   = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['service', 'phase'], name='unique_service_phase')
        ]


class ServiceHurdle(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    hurdle  = models.ForeignKey(Hurdle, on_delete=models.CASCADE)
    notes   = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['service', 'hurdle'], name='unique_service_hurdle')
        ]
