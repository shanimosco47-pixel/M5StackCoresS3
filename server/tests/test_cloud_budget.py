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

    def test_disabled_recipients_or_wrong_thresholds_are_not_a_verified_alert(self):
        expected = {'thresholdRules': [{'thresholdPercent': n, 'spendBasis': 'CURRENT_SPEND'}
                                       for n in (0.5, 0.8, 1.0)],
                    'notificationsRule': {'enableProjectLevelRecipients': True,
                                          'disableDefaultIamRecipients': False}}
        for changes in ({'thresholdRules': [{'thresholdPercent': 10}]}, {'thresholdRules': []},
                        {'thresholdRules': [{'thresholdPercent': n, 'spendBasis': 'FORECASTED_SPEND'}
                                            for n in (0.5, 0.8, 1.0)]},
                        {'notificationsRule': {'enableProjectLevelRecipients': False,
                                               'disableDefaultIamRecipients': True}},
                        {'notificationsRule': {'enableProjectLevelRecipients': True,
                                               'disableDefaultIamRecipients': True}},
                        {'notificationsRule': {}}):
            self.assertFalse(bootstrap.notification_settings_match(expected | changes, expected))
        actual = {'thresholdRules': [{'thresholdPercent': n} for n in (1.0, 0.8, 0.5)],
                  'notificationsRule': {'enableProjectLevelRecipients': True}}
        self.assertTrue(bootstrap.notification_settings_match(actual, expected))
        unspecified = actual | {'thresholdRules': [{'thresholdPercent': n, 'spendBasis': 'BASIS_UNSPECIFIED'}
                                                   for n in (0.5, 0.8, 1.0)]}
        self.assertTrue(bootstrap.notification_settings_match(unspecified, expected))
