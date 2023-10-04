"""Models for Blueprints."""

from typing import List

from django.contrib.auth.models import Permission, User
from django.db import models
from django.utils.translation import gettext_lazy as _
from esi.errors import TokenError
from esi.models import Token
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.evelinks import dotlan
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.django import users_with_permission
from app_utils.logging import LoggerAddTag

from . import __title__
from .decorators import fetch_token_for_owner
from .managers import BlueprintManager, LocationManager, OwnerManager, RequestManager
from .providers import esi
from .validators import validate_material_efficiency, validate_time_efficiency

NAMES_MAX_LENGTH = 100

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def get_or_create_location_async(location_id: int, token: Token) -> "Location":
    """Get or create a location sync - helper function."""
    obj, _ = Location.objects.get_or_create_esi_async(id=location_id, token=token)
    return obj


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Can access this app"),
            ("request_blueprints", "Can request blueprints"),
            ("manage_requests", "Can review and accept blueprint requests"),
            ("add_personal_blueprint_owner", "Can add personal blueprint owners"),
            ("add_corporate_blueprint_owner", "Can add corporate blueprint owners"),
            ("view_alliance_blueprints", "Can view alliance's blueprints"),
            ("view_blueprint_locations", "Can view the location of all blueprints"),
            ("view_industry_jobs", "Can view details about running industry jobs"),
        )


class Owner(models.Model):
    """A corporation that owns blueprints"""

    corporation = models.OneToOneField(
        EveCorporationInfo,
        default=None,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Corporation owning blueprints, if this is a 'corporate' owner",
        related_name="+",
    )
    character = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        help_text="character used for syncing blueprints",
        related_name="+",
    )
    is_active = models.BooleanField(
        default=True,
        help_text=("whether this owner is currently included in the sync process"),
    )

    objects = OwnerManager()

    class Meta:
        default_permissions = ()

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        try:
            if self.corporation:
                return self.corporation.corporation_name
            return self.eve_character_strict.character_name
        except (ValueError, AttributeError):
            return ""

    @property
    def corporation_strict(self) -> EveCorporationInfo:
        if not self.corporation:
            raise ValueError("No corporation defined")
        return self.corporation

    @property
    def eve_character_strict(self) -> EveCharacter:
        if not self.character or not self.character.character:
            raise ValueError("No character defined")
        return self.character.character

    def update_locations_esi(self):
        if self.corporation:
            assets = self._fetch_corporate_assets()
            token = self.valid_token(
                [
                    "esi-universe.read_structures.v1",
                    "esi-assets.read_corporation_assets.v1",
                ]
            )
        else:
            assets = self._fetch_personal_assets()
            token = self.valid_token(
                ["esi-universe.read_structures.v1", "esi-assets.read_assets.v1"]
            )

        asset_ids = []
        asset_locations = {}
        assets_by_id = {}
        for asset in assets:
            asset_ids.append(asset["item_id"])
            assets_by_id[asset["item_id"]] = asset

        for asset in assets:
            if asset["location_id"] in asset_ids:
                location_id = asset["location_id"]
                if asset_locations.get(location_id):
                    asset_locations[location_id].append(asset["item_id"])
                else:
                    asset_locations[location_id] = [asset["item_id"]]

        for location_id in asset_locations.keys():
            asset = assets_by_id[location_id]
            parent_location = asset["location_id"]
            parent = get_or_create_location_async(parent_location, token=token)
            eve_type, _ = EveType.objects.get_or_create_esi(id=asset["type_id"])
            Location.objects.update_or_create(
                id=location_id, defaults={"parent": parent, "eve_type": eve_type}
            )

    def update_blueprints_esi(self):
        """Update all blueprints from ESI."""

        blueprint_ids_to_remove = list(
            self.blueprints.values_list("item_id", flat=True)
        )
        if self.corporation:
            blueprints = self._fetch_corporate_blueprints()
            token = self.valid_token(
                [
                    "esi-universe.read_structures.v1",
                    "esi-corporations.read_blueprints.v1",
                ]
            )
        else:
            blueprints = self._fetch_personal_blueprints()
            token = self.valid_token(
                [
                    "esi-universe.read_structures.v1",
                    "esi-characters.read_blueprints.v1",
                ]
            )

        for blueprint in blueprints:
            runs = blueprint["runs"]
            if runs < 1:
                runs = None
            quantity = blueprint["quantity"]
            if quantity < 0:
                quantity = 1
            original = self.blueprints.filter(item_id=blueprint["item_id"]).first()

            location_flag = Blueprint.LocationFlag.from_esi_data(
                blueprint["location_flag"]
            )
            eve_type, _ = EveType.objects.get_or_create_esi(id=blueprint["type_id"])
            if original is not None:
                # We've seen this blueprint coming from ESI, so we know it shouldn't be deleted
                blueprint_ids_to_remove.remove(original.item_id)
                original.location = get_or_create_location_async(
                    blueprint["location_id"],
                    token=token,
                )
                original.location_flag = location_flag
                original.eve_type = eve_type
                original.runs = runs
                original.material_efficiency = blueprint["material_efficiency"]
                original.time_efficiency = blueprint["time_efficiency"]
                original.quantity = quantity
                original.save()
            else:
                self.blueprints.create(
                    location=get_or_create_location_async(
                        blueprint["location_id"], token=token
                    ),
                    location_flag=location_flag,
                    eve_type=eve_type,
                    item_id=blueprint["item_id"],
                    runs=runs,
                    material_efficiency=blueprint["material_efficiency"],
                    time_efficiency=blueprint["time_efficiency"],
                    quantity=quantity,
                )

        Blueprint.objects.filter(pk__in=blueprint_ids_to_remove).delete()

    def update_industry_jobs_esi(self):
        """updates all blueprints from ESI"""

        if self.is_active:
            job_ids_to_remove = list(
                IndustryJob.objects.filter(owner=self).values_list("id", flat=True)
            )
            if self.corporation:
                jobs = self._fetch_corporate_industry_jobs()
                token = self.valid_token(
                    [
                        "esi-universe.read_structures.v1",
                        "esi-industry.read_corporation_jobs.v1",
                    ]
                )
            else:
                jobs = self._fetch_personal_industry_jobs()
                token = self.valid_token(
                    [
                        "esi-universe.read_structures.v1",
                        "esi-industry.read_character_jobs.v1",
                    ]
                )

            for job in jobs:
                original = IndustryJob.objects.filter(
                    owner=self, id=job["job_id"]
                ).first()
                blueprint = Blueprint.objects.filter(pk=job["blueprint_id"]).first()
                if blueprint is not None:
                    if original is not None:
                        # We've seen this job coming from ESI, so we know it shouldn't be deleted
                        job_ids_to_remove.remove(original.id)
                        original.status = job["status"]
                        original.save()
                    else:
                        # Reject personal listings of corporate jobs and visa-versa
                        if blueprint.owner == self:
                            installer = EveCharacter.objects.get_character_by_id(
                                job["installer_id"]
                            )
                            if not installer:
                                installer = EveCharacter.objects.create_character(
                                    job["installer_id"]
                                )
                            IndustryJob.objects.create(
                                id=job["job_id"],
                                activity=job["activity_id"],
                                owner=self,
                                location=get_or_create_location_async(
                                    job["output_location_id"],
                                    token=token,
                                ),
                                blueprint=Blueprint.objects.get(pk=job["blueprint_id"]),
                                installer=installer,
                                runs=job["runs"],
                                start_date=job["start_date"],
                                end_date=job["end_date"],
                                status=job["status"],
                            )
                else:
                    blueprint_id = job["blueprint_id"]
                    logger.warning(f"Unmatchable blueprint ID: {blueprint_id}")
            IndustryJob.objects.filter(pk__in=job_ids_to_remove).delete()

    @fetch_token_for_owner(["esi-assets.read_corporation_assets.v1"])
    def _fetch_corporate_assets(self, token) -> list:
        return esi.client.Assets.get_corporations_corporation_id_assets(
            corporation_id=self.corporation_strict.corporation_id,
            token=token.valid_access_token(),
        ).results()

    @fetch_token_for_owner(["esi-assets.read_assets.v1"])
    def _fetch_personal_assets(self, token) -> list:
        return esi.client.Assets.get_characters_character_id_assets(
            character_id=self.eve_character_strict.character_id,
            token=token.valid_access_token(),
        ).results()

    @fetch_token_for_owner(["esi-corporations.read_blueprints.v1"])
    def _fetch_corporate_blueprints(self, token) -> list:
        blueprints = esi.client.Corporation.get_corporations_corporation_id_blueprints(
            corporation_id=self.corporation_strict.corporation_id,
            token=token.valid_access_token(),
        ).results()
        return blueprints

    @fetch_token_for_owner(["esi-characters.read_blueprints.v1"])
    def _fetch_personal_blueprints(self, token) -> list:
        blueprints = esi.client.Character.get_characters_character_id_blueprints(
            character_id=self.eve_character_strict.character_id,
            token=token.valid_access_token(),
        ).results()
        return blueprints

    @fetch_token_for_owner(["esi-industry.read_corporation_jobs.v1"])
    def _fetch_corporate_industry_jobs(self, token) -> list:
        jobs = esi.client.Industry.get_corporations_corporation_id_industry_jobs(
            corporation_id=self.corporation_strict.corporation_id,
            token=token.valid_access_token(),
        ).results()
        return jobs

    @fetch_token_for_owner(["esi-industry.read_character_jobs.v1"])
    def _fetch_personal_industry_jobs(self, token) -> list:
        jobs = esi.client.Industry.get_characters_character_id_industry_jobs(
            character_id=self.eve_character_strict.character_id,
            token=token.valid_access_token(),
        ).results()
        return jobs

    def valid_token(self, scopes) -> Token:
        """Return a valid token for the owner or raise exception."""
        token = (
            Token.objects.filter(
                user=self.character.user,
                character_id=self.eve_character_strict.character_id,
            )
            .require_scopes(scopes)
            .require_valid()
            .first()
        )
        if not token:
            raise TokenError(f"{self}: No valid token found with sufficient scopes")

        return token


class Blueprint(models.Model):
    class LocationFlag(models.TextChoices):
        ASSET_SAFETY = "AssetSafety", _("Asset Safety")
        AUTO_FIT = "AutoFit", _("Auto Fit")
        BONUS = "Bonus", _("Bonus")
        BOOSTER = "Booster", _("Booster")
        BOOSTER_BAY = "BoosterBay", _("Booster Hold")
        CAPSULE = "Capsule", _("Capsule")
        CARGO = "Cargo", _("Cargo")
        CORP_DELIVERIES = "CorpDeliveries", _("Corp Deliveries")
        CORP_S_A_G_1 = "CorpSAG1", _("Corp Security Access Group 1")
        CORP_S_A_G_2 = "CorpSAG2", _("Corp Security Access Group 2")
        CORP_S_A_G_3 = "CorpSAG3", _("Corp Security Access Group 3")
        CORP_S_A_G_4 = "CorpSAG4", _("Corp Security Access Group 4")
        CORP_S_A_G_5 = "CorpSAG5", _("Corp Security Access Group 5")
        CORP_S_A_G_6 = "CorpSAG6", _("Corp Security Access Group 6")
        CORP_S_A_G_7 = "CorpSAG7", _("Corp Security Access Group 7")
        CRATE_LOOT = "CrateLoot", _("Crate Loot")
        DELIVERIES = "Deliveries", _("Deliveries")
        DRONE_BAY = "DroneBay", _("Drone Bay")
        DUST_BATTLE = "DustBattle", _("Dust Battle")
        DUST_DATABANK = "DustDatabank", _("Dust Databank")
        FIGHTER_BAY = "FighterBay", _("Fighter Bay")
        FIGHTER_TUBE_0 = "FighterTube0", _("Fighter Tube 0")
        FIGHTER_TUBE_1 = "FighterTube1", _("Fighter Tube 1")
        FIGHTER_TUBE_2 = "FighterTube2", _("Fighter Tube 2")
        FIGHTER_TUBE_3 = "FighterTube3", _("Fighter Tube 3")
        FIGHTER_TUBE_4 = "FighterTube4", _("Fighter Tube 4")
        FLEET_HANGAR = "FleetHangar", _("Fleet Hangar")
        FRIGATE_ESCAPE_BAY = "FrigateEscapeBay", _("Frigate escape bay Hangar")
        HANGAR = "Hangar", _("Hangar")
        HANGAR_ALL = "HangarAll", _("Hangar All")
        HI_SLOT_0 = "HiSlot0", _("High power slot 1")
        HI_SLOT_1 = "HiSlot1", _("High power slot 2")
        HI_SLOT_2 = "HiSlot2", _("High power slot 3")
        HI_SLOT_3 = "HiSlot3", _("High power slot 4")
        HI_SLOT_4 = "HiSlot4", _("High power slot 5")
        HI_SLOT_5 = "HiSlot5", _("High power slot 6")
        HI_SLOT_6 = "HiSlot6", _("High power slot 7")
        HI_SLOT_7 = "HiSlot7", _("High power slot 8")
        HIDDEN_MODIFIERS = "HiddenModifiers", _("Hidden Modifiers")
        IMPLANT = "Implant", _("Implant")
        IMPOUNDED = "Impounded", _("Impounded")
        JUNKYARD_REPROCESSED = "JunkyardReprocessed", _(
            "This item was put into a junkyard through reprocessing."
        )
        JUNKYARD_TRASHED = "JunkyardTrashed", _(
            "This item was put into a junkyard through being trashed by its owner."
        )
        LO_SLOT_0 = "LoSlot0", _("Low power slot 1")
        LO_SLOT_1 = "LoSlot1", _("Low power slot 2")
        LO_SLOT_2 = "LoSlot2", _("Low power slot 3")
        LO_SLOT_3 = "LoSlot3", _("Low power slot 4")
        LO_SLOT_4 = "LoSlot4", _("Low power slot 5")
        LO_SLOT_5 = "LoSlot5", _("Low power slot 6")
        LO_SLOT_6 = "LoSlot6", _("Low power slot 7")
        LO_SLOT_7 = "LoSlot7", _("Low power slot 8")
        LOCKED = "Locked", _("Locked item, can not be moved unless unlocked")
        MED_SLOT_0 = "MedSlot0", _("Medium power slot 1")
        MED_SLOT_1 = "MedSlot1", _("Medium power slot 2")
        MED_SLOT_2 = "MedSlot2", _("Medium power slot 3")
        MED_SLOT_3 = "MedSlot3", _("Medium power slot 4")
        MED_SLOT_4 = "MedSlot4", _("Medium power slot 5")
        MED_SLOT_5 = "MedSlot5", _("Medium power slot 6")
        MED_SLOT_6 = "MedSlot6", _("Medium power slot 7")
        MED_SLOT_7 = "MedSlot7", _("Medium power slot 8")
        OFFICE_FOLDER = "OfficeFolder", _("Office Folder")
        PILOT = "Pilot", _("Pilot")
        PLANET_SURFACE = "PlanetSurface", _("Planet Surface")
        QUAFE_BAY = "QuafeBay", _("Quafe Bay")
        QUANTUM_CORE_ROOM = "QuantumCoreRoom", _("Quantum Core Room")
        REWARD = "Reward", _("Reward")
        RIG_SLOT_0 = "RigSlot0", _("Rig power slot 1")
        RIG_SLOT_1 = "RigSlot1", _("Rig power slot 2")
        RIG_SLOT_2 = "RigSlot2", _("Rig power slot 3")
        RIG_SLOT_3 = "RigSlot3", _("Rig power slot 4")
        RIG_SLOT_4 = "RigSlot4", _("Rig power slot 5")
        RIG_SLOT_5 = "RigSlot5", _("Rig power slot 6")
        RIG_SLOT_6 = "RigSlot6", _("Rig power slot 7")
        RIG_SLOT_7 = "RigSlot7", _("Rig power slot 8")
        SECONDARY_STORAGE = "SecondaryStorage", _("Secondary Storage")
        SERVICE_SLOT_0 = "ServiceSlot0", _("Service Slot 0")
        SERVICE_SLOT_1 = "ServiceSlot1", _("Service Slot 1")
        SERVICE_SLOT_2 = "ServiceSlot2", _("Service Slot 2")
        SERVICE_SLOT_3 = "ServiceSlot3", _("Service Slot 3")
        SERVICE_SLOT_4 = "ServiceSlot4", _("Service Slot 4")
        SERVICE_SLOT_5 = "ServiceSlot5", _("Service Slot 5")
        SERVICE_SLOT_6 = "ServiceSlot6", _("Service Slot 6")
        SERVICE_SLOT_7 = "ServiceSlot7", _("Service Slot 7")
        SHIP_HANGAR = "ShipHangar", _("Ship Hangar")
        SHIP_OFFLINE = "ShipOffline", _("Ship Offline")
        SKILL = "Skill", _("Skill")
        SKILL_IN_TRAINING = "SkillInTraining", _("Skill In Training")
        SPECIALIZED_AMMO_HOLD = "SpecializedAmmoHold", _("Specialized Ammo Hold")
        SPECIALIZED_COMMAND_CENTER_HOLD = "SpecializedCommandCenterHold", _(
            "Specialized Command Center Hold"
        )
        SPECIALIZED_FUEL_BAY = "SpecializedFuelBay", _("Specialized Fuel Bay")
        SPECIALIZED_GAS_HOLD = "SpecializedGasHold", _("Specialized Gas Hold")
        SPECIALIZED_INDUSTRIAL_SHIP_HOLD = "SpecializedIndustrialShipHold", _(
            "Specialized Industrial Ship Hold"
        )
        SPECIALIZED_LARGE_SHIP_HOLD = "SpecializedLargeShipHold", _(
            "Specialized Large Ship Hold"
        )
        SPECIALIZED_MATERIAL_BAY = "SpecializedMaterialBay", _(
            "Specialized Material Bay"
        )
        SPECIALIZED_MEDIUM_SHIP_HOLD = "SpecializedMediumShipHold", _(
            "Specialized Medium Ship Hold"
        )
        SPECIALIZED_MINERAL_HOLD = "SpecializedMineralHold", _(
            "Specialized Mineral Hold"
        )
        SPECIALIZED_ORE_HOLD = "SpecializedOreHold", _("Specialized Ore Hold")
        SPECIALIZED_PLANETARY_COMMODITIES_HOLD = (
            "SpecializedPlanetaryCommoditiesHold",
            _("Specialized Planetary Commodities Hold"),
        )
        SPECIALIZED_SALVAGE_HOLD = "SpecializedSalvageHold", _(
            "Specialized Salvage Hold"
        )
        SPECIALIZED_SHIP_HOLD = "SpecializedShipHold", _("Specialized Ship Hold")
        SPECIALIZED_SMALL_SHIP_HOLD = "SpecializedSmallShipHold", _(
            "Specialized Small Ship Hold"
        )
        STRUCTURE_ACTIVE = "StructureActive", _("Structure Active")
        STRUCTURE_FUEL = "StructureFuel", _("Structure Fuel")
        STRUCTURE_INACTIVE = "StructureInactive", _("Structure Inactive")
        STRUCTURE_OFFLINE = "StructureOffline", _("Structure Offline")
        SUB_SYSTEM_BAY = "SubSystemBay", _("Sub System Bay")
        SUB_SYSTEM_SLOT_0 = "SubSystemSlot0", _("Sub System Slot 0")
        SUB_SYSTEM_SLOT_1 = "SubSystemSlot1", _("Sub System Slot 1")
        SUB_SYSTEM_SLOT_2 = "SubSystemSlot2", _("Sub System Slot 2")
        SUB_SYSTEM_SLOT_3 = "SubSystemSlot3", _("Sub System Slot 3")
        SUB_SYSTEM_SLOT_4 = "SubSystemSlot4", _("Sub System Slot 4")
        SUB_SYSTEM_SLOT_5 = "SubSystemSlot5", _("Sub System Slot 5")
        SUB_SYSTEM_SLOT_6 = "SubSystemSlot6", _("Sub System Slot 6")
        SUB_SYSTEM_SLOT_7 = "SubSystemSlot7", _("Sub System Slot 7")
        UNLOCKED = "Unlocked", _("Unlocked item, can be moved")
        WALLET = "Wallet", _("Wallet")
        WARDROBE = "Wardrobe", _("Wardrobe")
        UNDEFINED = "Undefined", _("undefined")

        @classmethod
        def from_esi_data(cls, data: str) -> "Blueprint.LocationFlag":
            try:
                return cls(data)
            except ValueError:
                return cls.UNDEFINED

    item_id = models.PositiveBigIntegerField(
        primary_key=True, help_text="The EVE Item ID of the blueprint"
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        related_name="blueprints",
        help_text="Corporation that owns the blueprint",
    )
    eve_type = models.ForeignKey(
        EveType, on_delete=models.CASCADE, related_name="+", help_text="Blueprint type"
    )
    location = models.ForeignKey(
        "Location",
        on_delete=models.CASCADE,
        related_name="blueprints",
        help_text="Blueprint location",
    )
    location_flag = models.CharField(
        help_text="Additional location information",
        choices=LocationFlag.choices,
        max_length=36,
    )
    quantity = models.PositiveIntegerField(help_text="Number of blueprints", default=1)
    runs = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Runs remaining or null if the blueprint is an original",
    )
    material_efficiency = models.PositiveIntegerField(
        help_text="Material efficiency of the blueprint",
        validators=[validate_material_efficiency],
    )
    time_efficiency = models.PositiveIntegerField(
        help_text="Time efficiency of the blueprint",
        validators=[validate_time_efficiency],
    )

    objects = BlueprintManager()

    @property
    def is_original(self):
        return not self.runs

    @property
    def location_flag_obj(self) -> "Blueprint.LocationFlag":
        return self.LocationFlag(self.location_flag)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return (
            self.eve_type.name + f" ({self.material_efficiency}/{self.time_efficiency})"
        )

    def has_industryjob(self):
        return hasattr(self, "industryjob") and self.industryjob is not None


class IndustryJob(models.Model):
    id = models.PositiveBigIntegerField(
        primary_key=True,
        help_text=("Eve Online job ID"),
    )

    class Activity(models.IntegerChoices):
        MANUFACTURING = 1, _("Manufacturing")
        RESEARCHING_TECHNOLOGY = 2, _("Researching Technology")
        RESEARCHING_TIME_EFFICIENCY = 3, _("Researching Time Efficiency")
        RESEARCHING_MATERIAL_EFFICIENCY = 4, _("Researching Material Efficiency")
        COPYING = 5, _("Copying")
        DUPLICATING = 6, _("Duplicating")
        REVERSE_ENGINEERING = 7, _("Reverse Engineering")
        INVENTING = 8, _("Inventing")
        REACTING = 9, _("Reacting")

    activity = models.PositiveIntegerField(choices=Activity.choices)
    location = models.ForeignKey(
        "Location",
        on_delete=models.CASCADE,
        help_text=(
            "Eve Online location ID of the facility in which the job is running"
        ),
        related_name="+",
    )
    blueprint = models.OneToOneField(
        Blueprint,
        on_delete=models.CASCADE,
        help_text=("Blueprint the job is running"),
    )
    installer = models.ForeignKey(
        EveCharacter,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    runs = models.PositiveIntegerField()
    status = models.CharField(
        choices=(
            ("active", "Active"),
            ("cancelled", "Cancelled"),
            ("delivered", "Delivered"),
            ("paused", "Paused"),
            ("ready", "Ready"),
            ("reverted", "Reverted"),
        ),
        max_length=10,
    )


class Location(models.Model):
    """An Eve Online location: Station or Upwell Structure or Solar System"""

    _SOLAR_SYSTEM_ID_START = 30_000_000
    _SOLAR_SYSTEM_ID_END = 33_000_000
    _STATION_ID_START = 60_000_000
    _STATION_ID_END = 64_000_000

    id = models.PositiveBigIntegerField(
        primary_key=True,
        help_text=(
            "Eve Online location ID, "
            "either item ID for stations or structure ID for structures"
        ),
    )
    parent = models.ForeignKey(
        "Location",
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        help_text=("Eve Online location ID of the parent object"),
        related_name="+",
    )

    name = models.CharField(
        max_length=NAMES_MAX_LENGTH,
        help_text="In-game name of this station or structure",
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    owner = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        help_text="corporation this station or structure belongs to",
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = LocationManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        if self.name:
            return self.name
        if self.eve_type:
            return str(self.eve_type)
        return f"Location #{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, name='{self.name}')"

    @property
    def is_empty(self) -> bool:
        return not self.eve_solar_system and not self.eve_type and not self.parent_id

    @property
    def solar_system_url(self) -> str:
        """returns dotlan URL for this solar system"""
        try:
            return dotlan.solar_system_url(self.eve_solar_system.name)
        except AttributeError:
            return ""

    @property
    def is_solar_system(self) -> bool:
        return self.is_solar_system_id(self.id)

    @property
    def is_station(self) -> bool:
        return self.is_station_id(self.id)

    @classmethod
    def is_solar_system_id(cls, location_id: int) -> bool:
        return cls._SOLAR_SYSTEM_ID_START <= location_id <= cls._SOLAR_SYSTEM_ID_END

    @classmethod
    def is_station_id(cls, location_id: int) -> bool:
        return cls._STATION_ID_START <= location_id <= cls._STATION_ID_END

    def full_qualified_name(self) -> str:
        """Return the full qualified name of this location."""
        if self.parent:
            return f"{self.parent.full_qualified_name()} - {str(self)}"
        return str(self)


class Request(models.Model):
    blueprint = models.ForeignKey(
        Blueprint,
        on_delete=models.CASCADE,
    )
    requesting_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="The requesting user",
    )
    fulfulling_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
        help_text="The user that fulfilled the request, if it has been fulfilled",
    )
    runs = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Runs requested or blank for maximum allowed",
    )
    STATUS_OPEN = "OP"
    STATUS_IN_PROGRESS = "IP"
    STATUS_FULFILLED = "FL"
    STATUS_CANCELLED = "CL"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_FULFILLED, "Fulfilled"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    status = models.CharField(
        help_text="Status of the blueprint request",
        choices=STATUS_CHOICES,
        max_length=2,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField(blank=True, null=True, db_index=True)

    objects = RequestManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return f"{self.requesting_user.profile.main_character.character_name}'s request for {self.blueprint.eve_type.name}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.pk}, "
            f"requesting_user='{self.requesting_user.profile.main_character.character_name}', "
            f"type_name='{self.eve_type.name}')"
        )

    def notify_new_request(self) -> None:
        for approver in self.approvers():
            notify(
                title=(
                    f"Blueprints: {self.blueprint.eve_type.name} has been requested"
                ),
                message=(
                    f"A copy of {self.blueprint.eve_type.name} has been "
                    f"requested by {self.requesting_user}."
                ),
                user=approver,
                level="info",
            )

    def notify_request_in_progress(self) -> None:
        notify(
            title=(f"Blueprints: {self.blueprint.eve_type.name} request in progress"),
            message=(
                f"{self.fulfulling_user} has started producing copies for "
                f"{self.blueprint.eve_type.name}."
            ),
            user=self.requesting_user,
            level="info",
        )
        other_approvers = set(self.approvers()) - {self.fulfulling_user}
        for approver in other_approvers:
            notify(
                title=(
                    f"Blueprints: {self.blueprint.eve_type.name} request in progress"
                ),
                message=(
                    f"{self.fulfulling_user} has started producing copies for "
                    f"{self.blueprint.eve_type.name} as requested by"
                    f"{self.requesting_user} "
                ),
                user=approver,
                level="info",
            )

    def notify_request_reopened(self, reopened_by: User) -> None:
        for user in set(self.approvers()) - {reopened_by} | {self.requesting_user}:
            notify(
                title=(f"Blueprints: {self.blueprint.eve_type.name} request re-opened"),
                message=(
                    f"{reopened_by} has re-opened the request for "
                    f"{self.blueprint.eve_type.name} by"
                    f"{self.requesting_user}"
                ),
                user=user,
                level="warning",
            )

    def notify_request_fulfilled(self) -> None:
        notify(
            title=(f"Blueprints: {self.blueprint.eve_type.name} request completed"),
            message=(
                f"{self.fulfulling_user} has finished producing copies for "
                f"{self.blueprint.eve_type.name}."
            ),
            user=self.requesting_user,
            level="success",
        )

    def notify_request_canceled_by_requestor(self) -> None:
        for approver in set(self.approvers()):
            notify(
                title=(f"Blueprints: {self.blueprint.eve_type.name} request canceled"),
                message=(
                    f"{self.requesting_user} has canceled his request for "
                    f"{self.blueprint.eve_type.name}."
                ),
                user=approver,
                level="danger",
            )

    def notify_request_canceled_by_approver(self, canceled_by: User) -> None:
        for approver in set(self.approvers()) - {canceled_by} | {self.requesting_user}:
            notify(
                title=(f"Blueprints: {self.blueprint.eve_type.name} request canceled"),
                message=(
                    f"{canceled_by} has canceled the request for "
                    f"{self.blueprint.eve_type.name} "
                    f"by {self.requesting_user}."
                ),
                user=approver,
                level="danger",
            )

    @classmethod
    def approvers(cls) -> List[User]:
        permission = Permission.objects.select_related("content_type").get(
            content_type__app_label=cls._meta.app_label, codename="manage_requests"
        )
        return users_with_permission(permission)
