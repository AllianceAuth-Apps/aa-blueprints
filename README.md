# AA Blueprints

An app for listing blueprints and managing member usage in an organization with Alliance Auth.

[![release](https://img.shields.io/pypi/v/aa-blueprints?label=release)](https://pypi.org/project/aa-blueprints/)
[![python](https://img.shields.io/pypi/pyversions/aa-blueprints)](https://pypi.org/project/aa-blueprints/)
[![django](https://img.shields.io/pypi/djversions/aa-blueprints?label=django)](https://pypi.org/project/aa-blueprints/)
[![CI/CD Pipeline](https://github.com/AllianceAuth-Apps/aa-blueprints/actions/workflows/ci-cd.yaml/badge.svg)](https://github.com/AllianceAuth-Apps/aa-blueprints/actions/workflows/ci-cd.yaml)
[![codecov](https://codecov.io/github/AllianceAuth-Apps/aa-blueprints/graph/badge.svg?token=oqzLcXHOmT)](https://codecov.io/github/AllianceAuth-Apps/aa-blueprints)
[![license](https://img.shields.io/badge/license-GPLv3-green)](https://github.com/AllianceAuth-Apps/aa-blueprints#GPL-3.0-1-ov-file)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![chat](https://img.shields.io/discord/790364535294132234)](https://discord.gg/zmh52wnfvM)

## Overview

### Features

- Lists all blueprints owned by corporation or alliance (configurable with permissions)
- Manage user requests for making copies of blueprints

>[!TIP]
> Blueprints sends Auth notifications to inform users about blueprint requests. If you like to get those as direct messages on Discord please consider also installing [Discord Notify](https://gitlab.com/ErikKalkoken/aa-discordnotify).

## Screenshots

### Library

![library](https://i.imgur.com/62eUbB8.png)

#### View Blueprint

![view-blueprint](https://i.imgur.com/g8ge0gA.png)

#### Create a Request

![create-request](https://i.imgur.com/MSt7mZg.png)

#### My Requests

![my-requests](https://i.imgur.com/0Tj5jo6.png)

#### Open Requests

![open-requests](https://i.imgur.com/pQMuLEQ.png)

#### Manage Blueprints

![manage-blueprints](https://i.imgur.com/ap1vc4h.png)

## Installation

### Requirements

AA Blueprints needs the app [django-eveuniverse](https://gitlab.com/ErikKalkoken/django-eveuniverse) to function. Please make sure it is installed before before continuing.

### Steps

#### Step 1 - Install the Package

Make sure you are in the virtual environment (venv) of your Alliance Auth installation. Then install the newest release from PyPI:

```sh
pip install aa-blueprints
```

#### Step 2 - Configure AA

- Add 'blueprints' to `INSTALLED_APPS` in `settings/local.py`.
- Add the following automated task definition:

```python
CELERYBEAT_SCHEDULE['blueprints_update_all_blueprints'] = {
    'task': 'blueprints.tasks.update_all_blueprints',
    'schedule': 10800, # 3 hours
}
CELERYBEAT_SCHEDULE['blueprints_update_all_industry_jobs'] = {
    'task': 'blueprints.tasks.update_all_industry_jobs',
    'schedule': 3600, # 1 hour
}
CELERYBEAT_SCHEDULE['blueprints_update_all_locations'] = {
    'task': 'blueprints.tasks.update_all_locations',
    'schedule': 43200, # 12 hours
}
```

#### Step 3 - Finalize App installation

Run migrations & copy static files:

```sh
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for Auth

#### Step 4 - Update EVE Online API Application

Update the Eve Online API app used for authentication in your AA installation to include the following scopes:

- `esi-assets.read_assets.v1`
- `esi-assets.read_corporation_assets.v1`
- `esi-characters.read_blueprints.v1`
- `esi-corporations.read_blueprints.v1`
- `esi-industry.read_character_jobs.v1`
- `esi-industry.read_corporation_jobs.v1`
- `esi-universe.read_structures.v1`

#### Step 5 - Data import

Load EVE Online type data from ESI:

```bash
python manage.py blueprints_load_types
```

## Permissions

| ID                               | Description                                  | Notes                                                                          |
|----------------------------------|----------------------------------------------|--------------------------------------------------------------------------------|
| `basic_access`                   | Can access this app                          |                                                                                |
| `request_blueprints`             | Can request blueprints                       |                                                                                |
| `manage_requests`                | Can review and accept blueprint requests     |                                                                                |
| `add_personal_blueprint_owner`   | Can add personal blueprint owners            |                                                                                |
| `add_corporate_blueprint_owner`  | Can add corporate blueprint owners           | :warning: Should only be given to directors or the CEO.                        |
| `view_alliance_blueprints`       | Can view alliance's blueprints               |                                                                                |
| `view_industry_jobs`             | Can view details about running industry jobs | :warning: This permission will let someone see _all_ industry job information. |

## Upgrading

See [UPGRADING.md](UPGRADING.md).

## Authors

The main authors (in alphabetical order):

- [Erik Kalkoken](https://gitlab.com/ErikKalkoken)
- [Rebecca Claire Murphy](https://gitlab.com/rcmurphy), aka Myrhea
- [Peter Pfeufer](https://gitlab.com/ppfeufer), aka Rounon Dax
