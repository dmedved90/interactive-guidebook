# DISCOVER Interactive Guidebook

> **EZSJ fork** of [LIFE-DISCOVER/interactive-guidebook](https://github.com/LIFE-DISCOVER/interactive-guidebook),
> running at <https://guidebook.ezsj.eu>. Additions: service duration, cost, cost estimate and
> provider (one-stop shop or external), and a thematic filter of the guidebook steps
> (building a solar power plant). Deployment of this instance: `compose.ezsj.yaml`, backup:
> `deploy/backup-ezsj.sh`. Upstream changes: `git fetch upstream && git merge upstream/main`.

A web application for energy agency managers who support initiators of **Community Energy
Projects (CEPs)** — from the first idea through planning and realisation to long-term operation.
It was developed in the EU LIFE project [DISCOVER](https://projectdiscover.eu/)
(LIFE22-CET-DISCOVER).

**Live demo: <https://guidebook.pixelenergy.at>**

- **Interactive guidebook** — general steps for each project phase, with country-specific
  support services (Austria, Bulgaria, Croatia, France, Italy). Public, no login needed.
- **Service catalog** — search and filter all services by phase and country. Public.
- **Initiators and projects** — managers keep records of initiators, their projects and the
  phase history (login required).
- **Applied services** — record which services were applied to a project and with what outcome.
- **Links for initiators** — a single-use link per applied service, with an optional personal
  message, lets an initiator read about the service and send a note back without an account.
- **Six languages** — English, German, French, Italian, Croatian and Bulgarian interface.
  Services are written in English and in their country's language, guidebook steps in all six
  languages; visitors can switch between English and the local text. Translations are marked
  as drafts until a native speaker has reviewed them.

**Suggesting changes to services or guidebook steps?** See [CONTRIBUTING.md](CONTRIBUTING.md) —
you can do it in the browser, no programming needed.

## Screenshots

**Interactive guidebook** — general steps per phase with the services of the selected country:

![Interactive guidebook with an opened step and its Austrian services](docs/images/guidebook.png)

**Service page** — official link, what the initiator needs to provide, the result, and a switch
between English and the local language:

![Service page of an Austrian service with the English/German switch](docs/images/service.png)

**Service catalog** — filter by phase and country, or search:

![Service catalog filtered to Italian services in the planning phase](docs/images/catalog.png)

## How it works

| Concept | Meaning |
|---|---|
| Phase | Planning, Realisation, Operation (fixed) |
| Guidebook step | A general step within a phase, e.g. "Permit – Building Regulations" |
| Service | Country-specific support for a step, e.g. how to get a building permit in Austria |
| Initiator | A person or organisation starting a CEP (a client of the energy agency) |
| Project | An initiator's energy project; it moves through the phases |
| Applied service | A service used for a project, with outcome notes and optional links for the initiator |

Countries, guidebook steps and services live as YAML files in [`data/`](data/README.md).
Every deploy loads them into the database (`python manage.py sync_content`), so the files in
this repository are the only place where this content is edited. The domain model is described in
[docs/specification.md](docs/specification.md).

## Tech stack

Django 6 on Python 3.12+ · SQLite · server-rendered templates · Gunicorn · WhiteNoise ·
Docker Compose with [Caddy](https://caddyserver.com/) (automatic HTTPS).

```
accounts/     users (log in with email), first-run setup, language preference
catalog/      phases, countries, guidebook steps, services; content sync (catalog/content.py)
initiators/   initiators, projects, applied services, links for initiators
guidebook/    project settings and URLs
data/         content files (countries, steps, services)
locale/       interface translations (.po files)
static/       CSS, JavaScript, images
templates/    shared templates (layout, home, error pages)
```

## Getting started (local development)

Requirements: Python 3.12 or newer. For updating translations: GNU gettext.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_content        # load countries, steps and services from data/
python manage.py compilemessages     # optional: translated interface
python manage.py runserver
```

Open http://127.0.0.1:8000/. On the first visit you create the administrator account; the page
asks for a setup code, which `python manage.py setup_code` prints.

Run the tests with `python manage.py test`.

## Configuration

All settings come from environment variables (see [.env.example](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | development key if `DJANGO_DEBUG=1` | Required in production |
| `DJANGO_DEBUG` | `1` | Set to `0` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated host names |
| `DJANGO_HTTPS` | off | `1` behind HTTPS: secure cookies, HSTS, HTTPS redirect |
| `DJANGO_DB_PATH` | `db.sqlite3` | SQLite database file |
| `DJANGO_SERVE_STATIC` | off | `1` lets the app serve its own static files (Docker) |
| `DJANGO_SUPERUSER_EMAIL` / `_PASSWORD` | empty | Create the administrator on first start instead of the setup page |
| `CONTENT_REPO_URL` | empty | Base URL for "Edit on GitHub" links in the admin |
| `SOURCE_CODE_URL` | this repository | Source code link in the footer; set empty to hide it |
| `DOMAIN` | — | Docker Compose: the public host name Caddy gets a certificate for |

## Deployment with Docker

```bash
cp .env.example .env      # set DOMAIN and DJANGO_SECRET_KEY
docker compose up -d --build
```

Caddy obtains and renews the HTTPS certificate for `DOMAIN`. The database lives in the Docker
volume `db`; back it up regularly, e.g.
`docker compose exec web python -c "import sqlite3; sqlite3.connect('/data/db.sqlite3').backup(sqlite3.connect('/data/backup.sqlite3'))"`.

Changes merged into `main` are deployed automatically by GitHub Actions
([.github/workflows](.github/workflows)); see [docs/deployment.md](docs/deployment.md).

## Translations

Interface texts are in `locale/<language>/LC_MESSAGES/django.po`. After changing templates or
Python strings, run `python manage.py makemessages -l de -l fr -l it -l hr -l bg` and update the
translations; the Docker build compiles them. Corrections from native speakers are very welcome.

## Using the guidebook

Everyone is welcome to use the Interactive Guidebook — run it for your own region or energy
agency, adapt the services and steps to your country, translate it, or build on the code. It is
free software under the [European Union Public Licence v. 1.2](LICENSE) (EUPL-1.2).

If you use it, we would be happy if you name the original project, for example:

> Based on the DISCOVER Interactive Guidebook (LIFE22-CET-DISCOVER),
> <https://github.com/LIFE-DISCOVER/interactive-guidebook>

This is a request, not an additional licence condition; the terms of the EUPL apply.

## Disclaimer

The software and its content are provided **"as is"**, without warranty of any kind, express or
implied. The authors and the partners of the DISCOVER project accept **no responsibility or
liability for any damage** arising from the use of the software or its content.

The guidebook steps and services are general information compiled with care. They are not legal,
technical, tax or financial advice and may be incomplete or out of date; always check with the
responsible authorities and qualified professionals. The binding terms are set out in the
disclaimer of warranty and the disclaimer of liability of the [EUPL](LICENSE) (sections 7 and 8).

## License

[European Union Public Licence v. 1.2](LICENSE) (EUPL-1.2). The DISCOVER name and logo belong to
the DISCOVER consortium.

## Project partners and funding

The Interactive Guidebook was developed in the project **DISCOVER — Developing Integrated
Services for COmmunity energy to accelerate Valid Energy Transition** (LIFE22-CET-DISCOVER,
grant agreement 101120622, December 2023 – November 2026), which runs local hubs for Community
Energy Projects in five European regions.

| Partner | Country |
|---|---|
| [AISFOR SRL](https://www.aisfor.it/) (coordinator) | Italy |
| [AG.EN.A. – Agenzia per l'Energia e l'Ambiente della Provincia di Teramo](https://www.agenateramo.it/) | Italy |
| [Agence Parisienne du Climat](https://www.apc-paris.com/) | France |
| [Udruga bez granica](https://bezgranica.hr/) | Croatia |
| [Institute for Entrepreneurship, Sustainable Development and Innovation (IESDI)](https://institute-esdi.org/) | Bulgaria |
| [Pixel Energy Solutions GmbH](https://www.pixelenergy.at/) | Austria |

More about the project: [projectdiscover.eu](https://projectdiscover.eu/) ·
[EU LIFE project page](https://webgate.ec.europa.eu/life/publicWebsite/project/LIFE22-CET-DISCOVER-101120622/developing-integrated-services-for-community-energy-to-accelerate-valid-energy-transition)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/eu-cofunded-dark.png">
  <img src="docs/images/eu-cofunded.png" alt="Co-funded by the European Union" height="60">
</picture>

Co-funded by the European Union. Views and opinions expressed are however those of the
author(s) only and do not necessarily reflect those of the European Union or CINEA. Neither the
European Union nor the granting authority can be held responsible for them.
