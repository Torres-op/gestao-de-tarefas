from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from .forms import PeriodForm


class PeriodLimitTests(SimpleTestCase):
    def test_start_alone_cannot_open_a_period_longer_than_three_years(self):
        start = timezone.localdate() - timedelta(days=4 * 365)
        form = PeriodForm(data={"start": start.isoformat()})
        self.assertFalse(form.is_valid())
        self.assertIn("start", form.errors)

    def test_start_alone_within_three_years_is_accepted(self):
        start = timezone.localdate() - timedelta(days=365)
        form = PeriodForm(data={"start": start.isoformat()})
        self.assertTrue(form.is_valid(), form.errors)

    def test_explicit_period_longer_than_three_years_is_refused(self):
        form = PeriodForm(data={"start": "2020-01-01", "end": "2024-01-01"})
        self.assertFalse(form.is_valid())
        self.assertIn("end", form.errors)
