"""Guidebook content (countries, steps, services) stored as YAML files under data/.

The files in the repository are the single source of truth; ``sync_content`` makes the
database match them. Layout::

    data/countries.yaml                    list of {code, name, language}
    data/steps/<phase-slug>/<key>.yaml     one general guidebook step
    data/services/<country>/<key>.yaml     one country-specific service

A step's identity is its file name (``<key>``), so it may move between phase folders.
A service's identity is ``<country>/<key>``. Renaming a file means removing the old item
and adding a new one.

Translations are blocks keyed by language code inside the same file (``de: {name: …}``).
A service may only have a block for its country's language; a step may have one for each
interface language except English. Empty translated fields fall back to English.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from .models import (
    PROVIDER_CHOICES, THEMES, Country, GeneralStep, Phase, Service, ServicePhase, ServiceTranslation,
    StepTranslation,
)

CONTENT_DIR = Path(settings.BASE_DIR) / 'data'

KEY_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
URL_RE = re.compile(r'^https?://\S+$')
# "AT: …", "BG 01: …", "BG 08.1: …" — the country prefix is not part of the file name.
NAME_PREFIX_RE = re.compile(r'^[A-Z]{2}(?:\s*\d+(?:\.\d+)*)?:\s*')

STEP_FIELDS = {
    # yaml key: (model field, required, max length)
    'title': ('title', True, 200),
    'sort_order': ('sort_order', True, None),
    'topic': ('topic', False, 50),
    'description': ('description', False, None),
    'objective': ('objective', False, None),
    'description_long': ('description_long', False, None),
    'themes': (None, False, None),
}
SERVICE_FIELDS = {
    'name': ('name', True, 200),
    'step': (None, True, None),
    'summary': ('summary', True, 500),
    'description': ('description', False, None),
    'web_link': ('web_link', False, None),
    'stakeholder': ('stakeholder', False, 300),
    'input': ('service_input', False, None),
    'result': ('result', False, None),
    'remaining_hurdles': ('remaining_hurdles', False, None),
    'duration': ('duration', False, 100),
    'cost': ('cost', False, 200),
    'cost_estimate': ('cost_estimate', False, 200),
    'provider': ('provider', False, None),
    'extra_phases': (None, False, None),
    'active': ('is_active', False, None),
}
STEP_TRANSLATION_FIELDS = {
    'title': ('title', False, 200),
    'description': ('description', False, None),
    'objective': ('objective', False, None),
    'description_long': ('description_long', False, None),
    'reviewed': ('reviewed', False, None),
}
SERVICE_TRANSLATION_FIELDS = {
    'name': ('name', False, 200),
    'summary': ('summary', False, 500),
    'description': ('description', False, None),
    'stakeholder': ('stakeholder', False, 300),
    'input': ('service_input', False, None),
    'result': ('result', False, None),
    'remaining_hurdles': ('remaining_hurdles', False, None),
    'duration': ('duration', False, 100),
    'cost': ('cost', False, 200),
    'cost_estimate': ('cost_estimate', False, 200),
    'reviewed': ('reviewed', False, None),
}
BOOLEAN_FIELDS = {'active', 'reviewed'}
LIST_FIELDS = {'extra_phases', 'themes'}   # checked by the caller


def translation_languages():
    """Interface languages a text can be translated into (all but English)."""
    return [code for code, _name in settings.LANGUAGES if code != settings.LANGUAGE_CODE]


def derive_step_key(title):
    return slugify(title)[:100]


def derive_service_stem(name):
    return slugify(NAME_PREFIX_RE.sub('', name))[:100] or 'service'


class ContentError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f'{len(errors)} problem(s) in the content files:\n' + '\n'.join(errors))


@dataclass
class StepData:
    key: str
    phase: str
    path: str
    values: dict
    translations: dict = field(default_factory=dict)   # language -> {model field: value}


@dataclass
class ServiceData:
    key: str
    country: str
    stem: str
    step: str
    extra_phases: list
    path: str
    values: dict
    translations: dict = field(default_factory=dict)


@dataclass
class Content:
    countries: dict = field(default_factory=dict)   # code -> name
    languages: dict = field(default_factory=dict)   # country code -> language
    steps: dict = field(default_factory=dict)       # key -> StepData
    services: dict = field(default_factory=dict)    # "cc/stem" -> ServiceData


def _read_yaml(path, base, errors):
    rel = str(path.relative_to(base))
    try:
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f' (line {mark.line + 1}, column {mark.column + 1})' if mark else ''
        errors.append(f'{rel}{where}: invalid YAML: {exc.problem}')
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f'{rel}: cannot read: {exc}')
    return None


def _check_fields(data, spec, rel, errors):
    """Validate a mapping against a field spec; return {model_field: value}."""
    if not isinstance(data, dict):
        errors.append(f'{rel}: expected a set of "field: value" lines')
        return None
    unknown = sorted(set(data) - set(spec))
    if unknown:
        errors.append(f'{rel}: unknown field(s): {", ".join(unknown)} (allowed: {", ".join(spec)})')
    values = {}
    for name, (model_field, required, max_len) in spec.items():
        value = data.get(name)
        if value is None or value == '':
            if required:
                errors.append(f'{rel}: "{name}" is required')
            continue
        if name == 'sort_order':
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f'{rel}: "sort_order" must be a whole number')
                continue
        elif name in BOOLEAN_FIELDS:
            if not isinstance(value, bool):
                errors.append(f'{rel}: "{name}" must be true or false')
                continue
        elif name in LIST_FIELDS:
            continue
        else:
            if not isinstance(value, (str, int, float)):
                errors.append(f'{rel}: "{name}" must be text')
                continue
            value = str(value).strip()
            if max_len and len(value) > max_len:
                errors.append(f'{rel}: "{name}" is {len(value)} characters long (maximum {max_len})')
        if model_field:
            values[model_field] = value
    return values


def _split_translations(data, allowed, spec, rel, errors, hint):
    """Remove language blocks from ``data``; return {language: {model field: value}}."""
    if not isinstance(data, dict):
        return data, {}
    known = {code for code, _name in settings.LANGUAGES}
    data = dict(data)
    translations = {}
    for lang in sorted(set(data) & known):
        block = data.pop(lang)
        if lang not in allowed:
            if lang == settings.LANGUAGE_CODE:
                errors.append(f'{rel}: English texts go in the main fields, not in an "{lang}:" block')
            else:
                errors.append(f'{rel}: no "{lang}:" block allowed here ({hint})')
            continue
        values = _check_fields(block, spec, f'{rel} [{lang}]', errors)
        if values is not None:
            translations[lang] = values
    return data, translations


def load_content(base=CONTENT_DIR):
    """Read and validate all content files. Raises ContentError listing every problem."""
    base = Path(base)
    errors = []
    content = Content()
    phases = set(Phase.objects.values_list('slug', flat=True))

    countries_file = base / 'countries.yaml'
    countries = _read_yaml(countries_file, base, errors) if countries_file.exists() else None
    if not isinstance(countries, list):
        errors.append('countries.yaml: expected a list of "- code: XX / name: …" entries')
        countries = []
    languages = translation_languages()
    for entry in countries:
        if not isinstance(entry, dict) or not entry.get('code') or not entry.get('name'):
            errors.append(f'countries.yaml: every entry needs "code" and "name": {entry!r}')
            continue
        code = str(entry['code']).upper()
        if len(code) > 10 or len(str(entry['name'])) > 100:
            errors.append(f'countries.yaml: code or name too long: {entry!r}')
        language = entry.get('language')
        if language not in languages:
            errors.append(
                f'countries.yaml: {code} needs "language", one of: {", ".join(languages)}'
            )
        content.countries[code] = str(entry['name']).strip()
        content.languages[code] = language or ''

    for path in sorted((base / 'steps').glob('*/*.yaml')):
        rel = str(path.relative_to(base))
        phase, key = path.parent.name, path.stem
        if phase not in phases:
            errors.append(f'{rel}: unknown phase folder "{phase}" (use one of: {", ".join(sorted(phases))})')
        if not KEY_RE.match(key):
            errors.append(f'{rel}: file name must be lowercase words joined by "-"')
        if key in content.steps:
            errors.append(f'{rel}: a step "{key}" already exists in {content.steps[key].path}')
            continue
        data, translations = _split_translations(
            _read_yaml(path, base, errors), languages, STEP_TRANSLATION_FIELDS, rel, errors,
            f'steps can have: {", ".join(languages)}',
        )
        values = _check_fields(data, STEP_FIELDS, rel, errors)
        if values is not None:
            themes = data.get('themes') or []
            if not isinstance(themes, list) or any(t not in THEMES for t in themes):
                errors.append(f'{rel}: "themes" must be a list of: {", ".join(THEMES)}')
                themes = []
            values['themes'] = ','.join(themes)
            content.steps[key] = StepData(
                key=key, phase=phase, path=rel, values=values, translations=translations,
            )

    for path in sorted((base / 'services').glob('*/*.yaml')):
        rel = str(path.relative_to(base))
        country, stem = path.parent.name, path.stem
        if country.upper() not in content.countries or country != country.lower():
            errors.append(f'{rel}: folder "{country}" is not a lowercase country code from countries.yaml')
        if not KEY_RE.match(stem):
            errors.append(f'{rel}: file name must be lowercase words joined by "-"')
        language = content.languages.get(country.upper())
        data, translations = _split_translations(
            _read_yaml(path, base, errors), [language] if language else [], SERVICE_TRANSLATION_FIELDS,
            rel, errors, f'services of {country.upper()} can only have "{language}:"' if language
            else 'the country has no language in countries.yaml',
        )
        values = _check_fields(data, SERVICE_FIELDS, rel, errors)
        if values is None:
            continue
        step = str(data.get('step') or '')
        if step and step not in content.steps:
            errors.append(f'{rel}: step "{step}" does not exist in data/steps/')
        provider = values.get('provider', '')
        if provider and provider not in dict(PROVIDER_CHOICES):
            errors.append(f'{rel}: "provider" must be one of: {", ".join(dict(PROVIDER_CHOICES))}')
        link = values.get('web_link', '')
        if link and not URL_RE.match(link):
            errors.append(f'{rel}: "web_link" must start with https:// or http://')
        extra = data.get('extra_phases') or []
        if not isinstance(extra, list) or any(p not in phases for p in extra):
            errors.append(f'{rel}: "extra_phases" must be a list of: {", ".join(sorted(phases))}')
            extra = []
        key = f'{country}/{stem}'
        content.services[key] = ServiceData(
            key=key, country=country.upper(), stem=stem, step=step, extra_phases=extra, path=rel,
            values=values, translations=translations,
        )

    if errors:
        raise ContentError(errors)
    return content


@dataclass
class SyncReport:
    counts: dict = field(default_factory=dict)
    changes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add(self, kind, action, label):
        self.counts.setdefault(kind, {}).setdefault(action, 0)
        self.counts[kind][action] += 1
        if action != 'unchanged':
            self.changes.append(f'{action}: {kind} {label}')

    def summary(self):
        lines = []
        for kind in ('countries', 'steps', 'services', 'translations'):
            parts = [f'{n} {action}' for action, n in sorted(self.counts.get(kind, {}).items())]
            lines.append(f'{kind}: {", ".join(parts) or "none"}')
        return lines


def _apply(obj, values):
    """Set changed attributes; return True if anything changed."""
    changed = False
    for name, value in values.items():
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            changed = True
    return changed


def _unique_slug(base):
    slug, i = base[:150], 2
    while Service.objects.filter(slug=slug).exists():
        slug = f'{base[:145]}-{i}'
        i += 1
    return slug


def _sync_translations(model, owner_field, owner, label, wanted, existing, defaults, report):
    """Make ``owner``'s translations match ``wanted`` ({language: values})."""
    for lang, values in wanted.items():
        values = {**defaults, **values}
        translation = existing.pop((owner.pk, lang), None)
        if translation is None:
            model.objects.create(**{owner_field: owner}, language=lang, **values)
            report.add('translations', 'created', f'{label} [{lang}]')
        elif _apply(translation, values):
            translation.save()
            report.add('translations', 'updated', f'{label} [{lang}]')
        else:
            report.add('translations', 'unchanged', f'{label} [{lang}]')


STEP_TRANSLATION_DEFAULTS = {
    'title': '', 'description': '', 'objective': '', 'description_long': '', 'reviewed': False,
}
SERVICE_TRANSLATION_DEFAULTS = {
    'name': '', 'summary': '', 'description': '', 'stakeholder': '', 'service_input': '',
    'result': '', 'remaining_hurdles': '', 'duration': '', 'cost': '', 'cost_estimate': '',
    'reviewed': False,
}


def sync_content(content, dry_run=False):
    """Make the database match ``content``. With dry_run, report without saving."""
    report = SyncReport()
    with transaction.atomic():
        _sync(content, report)
        if dry_run:
            transaction.set_rollback(True)
    return report


def _sync(content, report):
    phases = {p.slug: p for p in Phase.objects.all()}

    countries = {}
    for code, name in content.countries.items():
        country = Country.objects.filter(code=code).first()
        if country is None:
            country = Country.objects.create(code=code, name=name, language=content.languages.get(code, ''))
            report.add('countries', 'created', code)
        elif _apply(country, {'name': name, 'language': content.languages.get(code, '')}):
            country.save()
            report.add('countries', 'updated', code)
        else:
            report.add('countries', 'unchanged', code)
        countries[code] = country

    steps = {}
    existing_steps = {s.source_key: s for s in GeneralStep.objects.exclude(source_key=None)}
    step_translations = {(t.step_id, t.language): t for t in StepTranslation.objects.all()}
    for key, data in content.steps.items():
        values = {**data.values, 'phase': phases[data.phase]}
        values.setdefault('topic', '')
        values.setdefault('themes', '')
        for optional in ('description', 'objective', 'description_long'):
            values.setdefault(optional, '')
        step = existing_steps.get(key)
        if step is None:
            step = GeneralStep.objects.create(source_key=key, **values)
            report.add('steps', 'created', key)
        elif _apply(step, values):
            step.save()
            report.add('steps', 'updated', key)
        else:
            report.add('steps', 'unchanged', key)
        steps[key] = step
        _sync_translations(
            StepTranslation, 'step', step, f'step {key}', data.translations, step_translations,
            STEP_TRANSLATION_DEFAULTS, report,
        )

    existing_services = {
        s.source_key: s for s in Service.objects.exclude(source_key=None).prefetch_related('servicephase_set')
    }
    service_translations = {(t.service_id, t.language): t for t in ServiceTranslation.objects.all()}
    for key, data in content.services.items():
        step = steps[data.step]
        values = {
            'description': '', 'web_link': '', 'stakeholder': '', 'service_input': '',
            'result': '', 'remaining_hurdles': '', 'duration': '', 'cost': '', 'cost_estimate': '',
            'provider': '', 'is_active': True,
            **data.values,
            'country': countries[data.country],
            'general_step': step,
        }
        service = existing_services.get(key)
        if service is None:
            service = Service.objects.create(
                source_key=key, slug=_unique_slug(f'{data.country.lower()}-{data.stem}'), **values,
            )
            action = 'created'
        else:
            action = 'updated' if _apply(service, values) else 'unchanged'
            if action == 'updated':
                service.save()
        wanted = {step.phase_id} | {phases[p].pk for p in data.extra_phases}
        current = {sp.phase_id for sp in service.servicephase_set.all()} if action != 'created' else set()
        if wanted != current:
            ServicePhase.objects.filter(service=service).exclude(phase_id__in=wanted).delete()
            for phase_id in wanted - current:
                ServicePhase.objects.create(service=service, phase_id=phase_id)
            if action == 'unchanged':
                action = 'updated'
        report.add('services', action, key)
        _sync_translations(
            ServiceTranslation, 'service', service, f'service {key}', data.translations,
            service_translations, SERVICE_TRANSLATION_DEFAULTS, report,
        )

    # Translations still in these maps were removed from the files.
    step_keys = {s.pk: s.source_key for s in existing_steps.values()}
    service_keys = {s.pk: s.source_key for s in existing_services.values()}
    for (step_id, lang), translation in step_translations.items():
        translation.delete()
        report.add('translations', 'deleted', f'step {step_keys.get(step_id, step_id)} [{lang}]')
    for (service_id, lang), translation in service_translations.items():
        translation.delete()
        report.add('translations', 'deleted', f'service {service_keys.get(service_id, service_id)} [{lang}]')

    # Removed from the files: services are deactivated (projects may still use them),
    # steps are deleted (their services' step is set to empty).
    for key, service in existing_services.items():
        if key not in content.services and service.is_active:
            service.is_active = False
            service.save(update_fields=['is_active', 'updated_at'])
            report.add('services', 'deactivated', key)
    for key, step in existing_steps.items():
        if key not in content.steps:
            step.delete()
            report.add('steps', 'deleted', key)

    unmanaged = Service.objects.filter(source_key=None).count()
    if unmanaged:
        report.warnings.append(f'{unmanaged} service(s) in the database are not linked to a content file.')
    unmanaged = GeneralStep.objects.filter(source_key=None).count()
    if unmanaged:
        report.warnings.append(f'{unmanaged} step(s) in the database are not linked to a content file.')
