"""A total-project alert must not silently become a service/label subset."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'bootstrap', Path(__file__).resolve().parents[2] / 'tools/cloud/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BudgetScopeTests(unittest.TestCase):
    def setUp(self):
        self.total = {'projects': ['projects/123'], 'calendarPeriod': 'MONTH'}

    def test_total_alert_rejects_additional_scope_filters(self):
        for extra in ({'services': ['services/run']}, {'labels': {'team': ['m5']}},
                      {'subaccounts': ['billingAccounts/other']}, {'creditTypes': ['PROMOTION']},
                      {'resourceAncestors': ['folders/123']},
                      {'creditTypesTreatment': 'EXCLUDE_ALL_CREDITS'}):
            with self.subTest(extra=extra):
                self.assertFalse(bootstrap.filters_match(self.total | extra, self.total))

    def test_api_defaults_and_empty_filters_preserve_total_scope(self):
        actual = self.total | {'creditTypesTreatment': 'INCLUDE_ALL_CREDITS', 'services': [],
                               'labels': {}, 'subaccounts': [], 'creditTypes': [], 'resourceAncestors': []}
        self.assertTrue(bootstrap.filters_match(actual, self.total))
        self.assertTrue(bootstrap.filters_match(self.total, self.total))

    def test_service_cap_still_requires_its_exact_service_project_and_credit_policy(self):
        cap = self.total | {'services': ['services/run'], 'creditTypesTreatment': 'EXCLUDE_ALL_CREDITS'}
        self.assertTrue(bootstrap.filters_match(cap, cap))
        for changes in ({'services': []}, {'services': ['services/run', 'services/other']},
                        {'projects': ['projects/other']}, {'creditTypesTreatment': 'INCLUDE_ALL_CREDITS'},
                        {'labels': {'team': ['m5']}}):
            self.assertFalse(bootstrap.filters_match(cap | changes, cap))
