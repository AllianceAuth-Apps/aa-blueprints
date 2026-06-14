"""Shared ESI client for Blueprints."""

from pathlib import Path

from esi.openapi_clients import ESIClientProvider

from blueprints import __version__

spec_file = Path(__file__).parent / "openapi_2025-12-16.json"

esi = ESIClientProvider(
    compatibility_date="2025-12-16",
    ua_appname="aa-blueprints",
    ua_version=__version__,
    operations=[
        "GetUniverseStationsStationId",
        "GetUniverseStructuresStructureId",
        "GetCorporationsCorporationIdAssets",
        "GetCharactersCharacterIdAssets",
        "GetCorporationsCorporationIdBlueprints",
        "GetCharactersCharacterIdBlueprints",
        "GetCorporationsCorporationIdIndustryJobs",
        "GetCharactersCharacterIdIndustryJobs",
    ],
    spec_file=spec_file,
)
