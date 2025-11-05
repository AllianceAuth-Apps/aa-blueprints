# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP-440](https://www.python.org/dev/peps/pep-0440/).

## [Unreleased]

## [2.0.0] - 2025-11-05

### Changed

- BREAKING CHANGE: Support dropped for AA3
- Templates migrated to AA4 / Bootstrap 5 - Big thanks to @Geuthur for the contribution!

## [1.8.0] - 2025-10-12

### Update notes

This update is critical in order to avoid potential service degradation related to the rate limit change of the ESI status endpoint on Oct 13, 2025. See [CHANGELOG](https://gitlab.com/ErikKalkoken/allianceauth-app-utils/-/blob/master/CHANGELOG.md#1270---2025-10-12) of app_utils for more information.

### Changed

- Updated tasks to work with changed status endpoint.

## [1.7.0] - 2024-01-16

### Changed

- Added support for AA4
- Fix pylint issues and refactor
- Fixed pylint issues and refactor
- Added pylint checks
- Improved test suite

## [1.6.0] - 2023-10-04

### Added

- Location details (e.g. Hangar) now shown for each blueprint
- Ability to enable and disable owners on the admin site

### Changed

- Now raises all token error types when encountering an issue
- Error logging delegated to celery for token errors
- Improved admin pages
- Refactoring

## [1.5.2] - 2023-10-02

### Changed

- Show structure names instead of system names for blueprint locations

## [1.5.1] - 2023-10-02

### Changed

- Now shoes full qualified name for blueprint location in info window
- Show more information and filters on admin site

### Fixed

- Does not show blueprints in containers when filtering by location

## [1.5.0] - 2023-10-01

### Added

- Shows quantity of blueprints on "Manage Blueprints" tab

### Fixed

- Does not show unknown locations in dropdown filter on "Library" tab

## [1.4.0] - 2023-09-23

### Changed

- Migrated to AA 3
- Migrated build process to PEP 621
- Updated main dependencies
- Refactoring
- Removed danger

## [1.3.0] - 2022-03-13

### Changed

- Drop support for Python 3.6
- Drop support for Django 3.1
- Replaced django-datatables-view with fork that this Django 4 compatible
- Django 4 compatibility fixes
- Update pre-commit
- Remove redundant dependencies

### Fixed

- [Compatibility] AA 3.x / Django 4 :: ImportError: cannot import name 'ugettext_lazy' from 'django.utils.translation'

Thanks to @ppfeufer for your contribution!

## [1.2.1] - 2022-02-22

### Fixed

- Variable name showing in notification instead of owner name when adding blueprint owner. (#13)

## [1.2.0] - 2021-11-18

### Added

- Send Auth notifications for user requests to get blueprints copies (#7)

### Changed

- Updated `swagger.json`
- Added CI tests for AA 2.9 / Django 3.2

## [1.1.3] - 2021-06-14

### Changed

- Migrated to allianceauth-app-utils
- Reduce DB calls and add index for speeding up counting open requests
- Reduce DB calls when fetching the blueprint list
- Add tests for finding and counting open requests for a user

### Fixed

- `KeyError: 'location_id'` (Issue #8)

## [1.1.2] - 2021-05-05

### Changed

- Search filter now matches pattens anywhere not only at the beginning of a string

### Fixed

- Remember last active tab (Issue #6)
- Empty owners breaks blueprint list.
- Empty owner can not be deleted.

## [1.1.1] - 2021-02-03

### Added

- Dropdown filter for owner to blueprint list page
- Permission to view blueprint locations

### Fixed

- Some locations not showing in the filter list properly

## [1.1.0] - 2021-01-15

### Changed

- Significantly reduced load time of blueprints page for large datasets

### Fixed

- Personal blueprints of alliance members not shown to users with alliance permission

## [1.0.3] - 2021-01-14

### Added

- Building python wheels in addition to source packages, for faster installation

## [1.0.2] - 2021-01-03

### Fixed

- Requests not showing for alts

## [1.0.1] - 2020-12-28

### Fixed

- Regression involving manually specified run counts

## [1.0.0] - 2020-12-28

### Added

- Proper BPC icon support

## [1.0.0b1] - 2020-12-18

### Added

- Ability to add personal blueprints
- Ability to remove blueprint owners
- Badge in the "Open Requests" tab counting open and in-progress requests
- Ability to see blueprints currently in use by industry jobs
- Localization

### Changed

- Reworked object model for better flexibility and performance
- Permissions moved to Blueprints >> General to avoid confusion

## [0.2.1] - 2020-12-18

### Changed

- Improved styling

### Fixed

- Ability to see blueprint request button without permissions
- Permission error viewing blueprint requests

## [0.2.0] - 2020-12-17

### Added

- Ability to request blueprint copies

### Fixed

- Added dependency on recent versions of celery to avoid issues with tasks

## [0.1.1] - 2020-12-14

### Fixed

- Small bug in Owner object

## [0.1.0] - 2020-12-14

### Fixed

- Removed debugging code

## [0.1.0b4] - 2020-12-14

### Added

- Quantity field to blueprint table

### Changed

- Abbreviated material / time efficiency headings to allow for more compact table layout

## [0.1.0b3] - 2020-12-13

### Added

- Filter to blueprint table

### Fixed

- Re-added some error handling code that shouldn't have been removed
- Usage of bootstrap classes
- Blueprint table header classes
- Menu icon was still using the old FA library, now it isn't

## [0.1.0b2] - 2020-12-11

### Added

- Location resolution and display for blueprints
- Mechanism to update swagger.json (`make update_swagger`)
- Management command to update all blueprints and locations

### Changed

- Updated swagger from latest EVE API
- Switched to decorators for fetching tokens in the `Owner` model

## [0.1.0b1] - 2020-12-09

### Added

- Transifex config / support commands to Makefile

## [0.1.0a3] - 2020-12-06

### Fixed

- Fixed pagination bug

## [0.1.0a2] - 2020-12-06

### Added

- Model help text refined
- Admin interface improved
  - Blueprints are now read-only
  - Blueprints are now searchable and display additional information on the list page.
- Increased recommended update interval to 3 hours

## [0.1.0a1] - 2020-12-06

### Added

- i18n support
- Management command to download blueprint types

## [0.1.0.dev2] - 2020-12-06

### Changed

- Removed default permissions for Location and Blueprint models

## [0.1.0.dev1] - 2020-12-06

### Added

- Initial Dev Release
