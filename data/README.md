# Guidebook content

These files are the source of the countries, guidebook steps and services shown in the app.
Every deploy loads them (`python manage.py sync_content`); editing them here is the only way to
change this content. See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to suggest a change.

```
countries.yaml                    the countries services exist for
steps/<phase>/<step>.yaml         general guidebook steps; <phase> is planning, realisation or operation
services/<country>/<service>.yaml country-specific services; <country> is a lowercase code from countries.yaml
```

File names are identities: use lowercase words joined by `-`, and do not rename existing files.
Long or multi-line texts use `|-` followed by the text indented on the next lines:

```yaml
description: |-
  First paragraph.

  Second paragraph.
```

## Guidebook step — `steps/<phase>/<step>.yaml`

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | Step title (max. 200 characters) |
| `sort_order` | yes | Position in the guidebook (whole number; lower comes first) |
| `topic` | no | Short tag, e.g. `Social`, `PV Plant`, `REC` (max. 50) |
| `description` | no | One or two sentences shown in the guidebook |
| `objective` | no | What the step should achieve |
| `description_long` | no | Longer explanation |
| `themes` | no | Thematic filters the step belongs to, e.g. `[solar]` (building a solar power plant) |

Moving a file to another phase folder moves the step (and its services) to that phase.

## Service — `services/<country>/<service>.yaml`

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Service name, conventionally starting with the country code, e.g. `'AT: Permit - Building Code'` (max. 200) |
| `step` | yes | File name (without `.yaml`) of the guidebook step this service belongs to |
| `summary` | yes | Short description shown in lists (max. 500 characters) |
| `description` | no | Further details shown on the service page |
| `web_link` | no | Official link; must start with `https://` or `http://` |
| `stakeholder` | no | Organisation offering the service (max. 300) |
| `input` | no | What the initiator needs to provide |
| `result` | no | What the service delivers |
| `remaining_hurdles` | no | Known difficulties |
| `duration` | no | Typical duration, e.g. `4-8 weeks` (max. 100) |
| `cost` | no | Cost category, e.g. `Medium` or `0.5% of the investment per year` (max. 200) |
| `cost_estimate` | no | Indicative cost, e.g. `1,500-4,000 EUR` (max. 200) |
| `provider` | no | Who delivers it: `oss` (the one-stop shop) or `external` (an external provider) |
| `extra_phases` | no | Further phases the service applies to, e.g. `[operation]` (its step's phase is always included) |
| `active` | no | `false` hides the service without deleting it |

## Translations

English is the main language: the fields above are always English. Translations go into a
block named after the language, in the same file:

```yaml
name: 'AT: Permit - Building Code'
step: permit-building-regulations
summary: Some PV installations need a building notification …
de:
  name: 'AT: Genehmigung - Bauordnung'
  summary: Manche PV-Anlagen brauchen eine Bauanzeige …
  reviewed: false
```

- **Services** have one translation, in their country's language (`language` in
  `countries.yaml`): `de` for Austria, `bg` for Bulgaria, `fr` for France, `hr` for Croatia,
  `it` for Italy.
- **Guidebook steps** can have a block for each of `de`, `fr`, `it`, `hr` and `bg`.
- Translatable fields: for services `name`, `summary`, `description`, `stakeholder`, `input`,
  `result`, `remaining_hurdles`, `duration`, `cost`, `cost_estimate`; for steps `title`, `description`, `objective`,
  `description_long`. Other fields (links, step, order, topic, themes, provider) are never translated.
- Every field in a block is optional; the site shows the English text where a translation is
  missing. Length limits are the same as for English.
- `reviewed: false` marks a draft; the site then shows a "draft translation" note. A native
  speaker sets `reviewed: true` after checking the text.
- When you change an English text, update the translation too, or set `reviewed: false` so
  it is checked again.

Visitors see the translation when the site is in that language; the service page also has a
switch between English and the local language.

## Formatting

Quote a text in `'…'` if it starts with a special character or contains `: ` (as service names
with a country prefix do).

## Countries — `countries.yaml`

```yaml
- code: AT
  name: Austria
  language: de
```

The code is also the folder name under `services/` (in lowercase). `language` is the language
of the country's service translations and must be one of the site's languages.
