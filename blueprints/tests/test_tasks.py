from unittest.mock import patch

from celery.exceptions import Retry

from django.test import override_settings

from app_utils.esi import EsiErrorLimitExceeded, EsiOffline
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from blueprints import tasks

from . import create_owner
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations

TASKS_PATH = "blueprints.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestTasks(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        load_locations()
        cls.owner = create_owner(character_id=1101, corporation_id=2101)

    @patch(TASKS_PATH + ".Owner.update_blueprints_esi")
    def test_update_all_blueprints(self, mock_update_blueprints_esi):
        tasks.update_all_blueprints()
        self.assertTrue(mock_update_blueprints_esi.called)

    @patch(TASKS_PATH + ".Owner.update_blueprints_esi")
    def test_update_blueprints_for_owner(self, mock_update_blueprints_esi):
        tasks.update_blueprints_for_owner(self.owner.pk)
        self.assertTrue(mock_update_blueprints_esi.called)

    @patch(TASKS_PATH + ".Owner.update_industry_jobs_esi")
    def test_update_all_industry_jobs(self, mock_update_industry_jobs_esi):
        tasks.update_all_industry_jobs()
        self.assertTrue(mock_update_industry_jobs_esi.called)

    @patch(TASKS_PATH + ".Owner.update_industry_jobs_esi")
    def test_update_industry_job_for_owner(self, mock_update_industry_jobs_esi):
        tasks.update_industry_jobs_for_owner(self.owner.pk)
        self.assertTrue(mock_update_industry_jobs_esi.called)

    @patch(TASKS_PATH + ".Owner.update_locations_esi")
    def test_update_all_locations(self, mock_update_locations_esi):
        tasks.update_all_locations()
        self.assertTrue(mock_update_locations_esi.called)

    @patch(TASKS_PATH + ".Owner.update_locations_esi")
    def test_update_locations_for_owner(self, mock_update_locations_esi):
        tasks.update_locations_for_owner(self.owner.pk)
        self.assertTrue(mock_update_locations_esi.called)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(TASKS_PATH + ".Location.objects.structure_update_or_create_esi")
class TestUpdateStructures(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.user, _ = create_user_from_evecharacter(1001)
        cls.token = cls.user.token_set.first()

    def test_should_update_structure(self, mock_structure_update_or_create_esi):
        # when
        tasks.update_structure_esi(id=1000000000001, token_pk=self.token.pk)

        # then
        self.assertTrue(mock_structure_update_or_create_esi.called)

    def test_should_retry_when_esi_is_offline(
        self, mock_structure_update_or_create_esi
    ):
        # given
        mock_structure_update_or_create_esi.side_effect = EsiOffline

        # when/then
        with self.assertRaises(Retry):
            tasks.update_structure_esi(id=1000000000001, token_pk=self.token.pk)

    def test_should_retry_when_esi_error_limit_is_exceeded(
        self, mock_structure_update_or_create_esi
    ):
        # given
        mock_structure_update_or_create_esi.side_effect = EsiErrorLimitExceeded

        # when/then
        with self.assertRaises(Retry):
            tasks.update_structure_esi(id=1000000000001, token_pk=self.token.pk)

    def test_should_abort_on_other_exceptions(
        self, mock_structure_update_or_create_esi
    ):
        # given
        mock_structure_update_or_create_esi.side_effect = OSError

        # when/then
        with self.assertRaises(OSError):
            tasks.update_structure_esi(id=1000000000001, token_pk=self.token.pk)
