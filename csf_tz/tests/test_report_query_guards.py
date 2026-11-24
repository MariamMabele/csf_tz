"""Offline unit tests for security and injection-safety guards in report query builders.

Each test covers a behaviour that was fixed and must not regress:

1. get_match_criterion — user permission conditions wrapped in ()
2. warehouse_type — ExistsCriterion (not f-string) in excise_duty_stock
3. department — isin() (not equality) in salary_slip_conditions
4. multi-value dimension — string wrapped in list before isin() in gl_entry_conditions
"""

import os
import unittest
from unittest.mock import patch

import frappe

_SITE = os.environ.get("TEST_SITE", "demo-16")
_SITES_PATH = os.environ.get("FRAPPE_SITES_PATH", "/home/mariam-dev/frappe-bench-v16/sites")


class TestMatchCriterionBrackets(unittest.TestCase):
	"""get_match_criterion must wrap conditions in () to prevent logic hijacking."""

	def test_condition_string_is_bracketed(self):
		"""A non-empty match condition must be returned as RawCriterion('(…)')."""
		from csf_tz.utils.query_builder import get_match_criterion

		raw = "company = '_TC'"
		with patch("csf_tz.utils.query_builder.build_match_conditions", return_value=raw):
			criterion = get_match_criterion("GL Entry")

		self.assertIsNotNone(criterion)
		# RawCriterion.get_sql() returns the wrapped string verbatim.
		sql = criterion.get_sql(quote_char="`")
		self.assertEqual(sql, f"({raw})")

	def test_or_condition_cannot_escape_brackets(self):
		"""An OR inside the match condition must not bleed out of the brackets."""
		from csf_tz.utils.query_builder import get_match_criterion

		raw = "company = '_TC' OR 1=1"
		with patch("csf_tz.utils.query_builder.build_match_conditions", return_value=raw):
			criterion = get_match_criterion("GL Entry")

		sql = criterion.get_sql(quote_char="`")
		# The SQL must start and end with the parentheses added by get_match_criterion.
		self.assertTrue(sql.startswith("("), f"SQL does not start with '(': {sql!r}")
		self.assertTrue(sql.endswith(")"), f"SQL does not end with ')': {sql!r}")

	def test_empty_conditions_returns_none(self):
		"""An unrestricted user (no match conditions) must return None."""
		from csf_tz.utils.query_builder import get_match_criterion

		for empty in ("", None):
			with patch("csf_tz.utils.query_builder.build_match_conditions", return_value=empty):
				self.assertIsNone(get_match_criterion("GL Entry"))


class TestWarehouseTypeBinding(unittest.TestCase):
	"""warehouse_type filter in excise_duty_stock must use an ExistsCriterion subquery."""

	@classmethod
	def setUpClass(cls):
		frappe.init(site=_SITE, sites_path=_SITES_PATH)

	@classmethod
	def tearDownClass(cls):
		frappe.destroy()

	def test_warehouse_type_produces_exists_subquery(self):
		"""get_stock_ledger_entries_query with warehouse_type must use EXISTS (…), not LIKE or =."""
		from csf_tz.csf_tz.report.excise_duty_stock import excise_duty_stock as eds

		filters = {
			"from_date": "2026-01-01",
			"to_date": "2026-12-31",
			"company": "_Test Company",
			"warehouse_type": "Bonded Warehouse",
		}
		sql = eds.get_stock_ledger_entries_query(filters, []).get_sql()
		self.assertIn("exists", sql.lower(), "warehouse_type filter must produce an EXISTS subquery")

	def test_warehouse_type_value_is_quoted_not_interpolated(self):
		"""The warehouse_type value must be quoted by qb, not interpolated raw.

		Inject a value that would break unparameterised SQL; it must appear
		properly quoted/escaped in the generated SQL rather than unquoted.
		"""
		from csf_tz.csf_tz.report.excise_duty_stock import excise_duty_stock as eds

		inject = "' OR 1=1 --"
		filters = {
			"from_date": "2026-01-01",
			"to_date": "2026-12-31",
			"company": "_Test Company",
			"warehouse_type": inject,
		}
		sql = eds.get_stock_ledger_entries_query(filters, []).get_sql()
		# qb wraps string values in single-quotes and escapes embedded quotes,
		# so the unescaped sequence "' OR 1=1" must not appear verbatim.
		self.assertNotIn("' OR 1=1", sql)


class TestDepartmentIsIn(unittest.TestCase):
	"""department filter in salary_slip_conditions must use isin(), not equality."""

	@classmethod
	def setUpClass(cls):
		frappe.init(site=_SITE, sites_path=_SITES_PATH)

	@classmethod
	def tearDownClass(cls):
		frappe.destroy()

	def test_department_filter_produces_in_clause(self):
		"""get_salary_slip_conditions with a department filter must generate IN (…)."""
		from csf_tz.csf_tz.report.salary_slip_conditions import get_salary_slip_conditions

		salary_slip = frappe.qb.DocType("Salary Slip")
		with patch(
			"csf_tz.csf_tz.report.salary_slip_conditions.get_departments",
			return_value=["Accounting", "Finance"],
		):
			conditions = get_salary_slip_conditions(
				salary_slip,
				filters={"company": "_Test Company", "department": "Accounting"},
				company_currency="TZS",
				from_date=None,
				to_date=None,
			)

		department_conds = [c for c in conditions if "department" in c.get_sql(quote_char="`").lower()]
		self.assertEqual(len(department_conds), 1)
		sql = department_conds[0].get_sql(quote_char="`")
		self.assertIn(" in ", sql.lower(), f"Expected IN clause, got: {sql!r}")

	def test_single_department_still_uses_isin(self):
		"""Even a single-item list must produce IN (…) so the calling path is consistent."""
		from csf_tz.csf_tz.report.salary_slip_conditions import get_salary_slip_conditions

		salary_slip = frappe.qb.DocType("Salary Slip")
		with patch(
			"csf_tz.csf_tz.report.salary_slip_conditions.get_departments",
			return_value=["Accounting"],
		):
			conditions = get_salary_slip_conditions(
				salary_slip,
				filters={"company": "_Test Company", "department": "Accounting"},
				company_currency="TZS",
				from_date=None,
				to_date=None,
			)

		dep_sql = next(
			c.get_sql(quote_char="`") for c in conditions if "department" in c.get_sql(quote_char="`").lower()
		)
		self.assertIn(" in ", dep_sql.lower())


class TestDimensionMultiValueFilter(unittest.TestCase):
	"""get_dimension_conditions must wrap a plain string in a list before isin()."""

	@classmethod
	def setUpClass(cls):
		frappe.init(site=_SITE, sites_path=_SITES_PATH)

	@classmethod
	def tearDownClass(cls):
		frappe.destroy()

	def _run_dimension_conditions(self, dimension_value):
		from csf_tz.csf_tz.report.gl_entry_conditions import get_dimension_conditions

		gl_entry = frappe.qb.DocType("GL Entry")
		dimension = frappe._dict(
			fieldname="branch",
			document_type="Branch",
			label="Branch",
			is_tree=False,
		)
		filters = frappe._dict(branch=dimension_value)

		with (
			patch(
				"csf_tz.csf_tz.report.gl_entry_conditions.get_accounting_dimensions",
				return_value=[dimension],
			),
			patch(
				"csf_tz.csf_tz.report.gl_entry_conditions.frappe.get_cached_value",
				return_value=False,
			),
		):
			return get_dimension_conditions(filters, gl_entry)

	def test_string_value_wrapped_in_list(self):
		"""A plain string dimension value must become isin(['Ilala']), not isin characters."""
		conditions = self._run_dimension_conditions("Ilala")
		self.assertEqual(len(conditions), 1)
		sql = conditions[0].get_sql(quote_char="`")
		self.assertIn("Ilala", sql)
		self.assertNotIn("'I'", sql)

	def test_list_value_passed_through(self):
		"""A list dimension value must still produce a valid IN clause."""
		conditions = self._run_dimension_conditions(["Ilala", "Mwenge"])
		self.assertEqual(len(conditions), 1)
		sql = conditions[0].get_sql(quote_char="`")
		self.assertIn("Ilala", sql)
		self.assertIn("Mwenge", sql)
		self.assertIn(" in ", sql.lower())
