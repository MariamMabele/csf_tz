"""Offline unit tests for accounts_receivable_multi_currency helpers."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from csf_tz.csf_tz.report.accounts_receivable_multi_currency import (
	accounts_receivable_multi_currency as armc,
)


def _make_dimension(fieldname, document_type, is_tree=False):
	return frappe._dict(fieldname=fieldname, document_type=document_type, is_tree=is_tree)


class TestAccountingDimensionFilter(FrappeTestCase):
	"""add_accounting_dimensions_filters must not expand a string into characters."""

	def _build_obj(self, dimension_value):
		"""Build a minimal ReceivablePayableReport-like object with one dimension filter."""
		obj = armc.ReceivablePayableReport.__new__(armc.ReceivablePayableReport)
		obj.filters = frappe._dict(branch=dimension_value)
		return obj

	def _run(self, dimension_value):
		obj = self._build_obj(dimension_value)
		gl_entry = frappe.qb.DocType("GL Entry")
		conditions = []
		dimension = _make_dimension("branch", "Branch", is_tree=False)
		with patch(
			"csf_tz.csf_tz.report.accounts_receivable_multi_currency"
			".accounts_receivable_multi_currency.get_accounting_dimensions",
			return_value=[dimension],
		), patch(
			"csf_tz.csf_tz.report.accounts_receivable_multi_currency"
			".accounts_receivable_multi_currency.frappe.get_cached_value",
			return_value=False,
		):
			obj.add_accounting_dimensions_filters(conditions, gl_entry)
		return conditions

	def test_string_value_wrapped_in_list(self):
		"""A plain string like 'Ilala' must produce isin(['Ilala']), not isin(('I','l','a','l','a'))."""
		conditions = self._run("Ilala")
		self.assertEqual(len(conditions), 1)
		sql = conditions[0].get_sql(quote_char="`", secondary_quote_char="`")
		# the isin value must contain the whole name, not individual characters
		self.assertIn("Ilala", sql)
		self.assertNotIn("'I'", sql)

	def test_list_value_passed_through(self):
		"""A list value must still work without double-wrapping."""
		conditions = self._run(["Ilala", "Mwenge"])
		self.assertEqual(len(conditions), 1)
		sql = conditions[0].get_sql(quote_char="`", secondary_quote_char="`")
		self.assertIn("Ilala", sql)
		self.assertIn("Mwenge", sql)
