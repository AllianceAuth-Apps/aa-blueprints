from unittest.mock import patch

from django.test import override_settings

from app_utils.testing import NoSocketsTestCase, reset_celery_once_locks

from blueprints import tasks
from blueprints.tests.testdata.factory import (
    OwnerCorporationFactory,
    UserMainDefaultFactory,
)

TASKS_PATH = "blueprints.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestTasks(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.owner = OwnerCorporationFactory()

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


@patch("celery.app.task.Context.called_directly", False)  # make retry work with eager
@override_settings(CELERY_ALWAYS_EAGER=True)
@patch(TASKS_PATH + ".Location.objects.structure_update_or_create_esi")
class TestUpdateStructures(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = UserMainDefaultFactory()
        cls.token = cls.user.token_set.first()

    def setUp(self):
        reset_celery_once_locks("blueprints")

    def test_should_update_structure(self, mock_structure_update_or_create_esi):
        # when
        tasks.update_structure_esi.delay(
            structure_id=1000000000001, token_pk=self.token.pk
        )

        # then
        self.assertEqual(mock_structure_update_or_create_esi.call_count, 1)
