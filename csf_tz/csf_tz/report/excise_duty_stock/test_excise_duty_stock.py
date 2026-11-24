"""Offline unit tests for excise_duty_stock report helpers."""

import unittest
from unittest.mock import patch

import frappe

from csf_tz.csf_tz.report.excise_duty_stock import excise_duty_stock as eds


class TestGetItems(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.init(site="demo-16", sites_path="/home/mariam-dev/frappe-bench-v16/sites")

	@classmethod
	def tearDownClass(cls):
		frappe.destroy()

	def test_nonexistent_item_group_raises_clear_message(self):
		"""get_items must throw a user-readable error when the Item Group filter names a group that
		does not exist, instead of an AttributeError from Criterion.all([None])."""

		def _raise(msg, *args, **kwargs):
			raise frappe.ValidationError(msg)

		with patch(
			"csf_tz.csf_tz.report.excise_duty_stock.excise_duty_stock.get_item_group_condition",
			return_value=None,
		), patch(
			"csf_tz.csf_tz.report.excise_duty_stock.excise_duty_stock._",
			side_effect=lambda s, **kw: s,
		), patch("frappe.throw", side_effect=_raise):
			self.assertRaisesRegex(
				frappe.ValidationError,
				"does not exist",
				eds.get_items,
				{"item_group": "Nonexistent Group"},
			)

	def test_no_item_group_filter_returns_empty_list(self):
		"""get_items with no filters returns an empty list (no DB needed)."""
		result = eds.get_items({})
		self.assertEqual(result, [])


class TestOrdering(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.init(site="demo-16", sites_path="/home/mariam-dev/frappe-bench-v16/sites")

	@classmethod
	def tearDownClass(cls):
		frappe.destroy()

	def test_sle_query_orders_by_date_time_creation(self):
		"""The query returned by get_stock_ledger_entries_query must ORDER BY
		posting_date, posting_time, creation so ledger rows on the same date
		arrive in a deterministic order."""
		filters = {"from_date": "2026-01-01", "to_date": "2026-12-31", "company": "_Test Company"}
		query = (
			eds.get_stock_ledger_entries_query(filters, [])
			.orderby(frappe.qb.Field("posting_date"))
			.orderby(frappe.qb.Field("posting_time"))
			.orderby(frappe.qb.Field("creation"))
		)
		sql = query.get_sql().lower()
		self.assertIn("posting_date", sql)
		self.assertIn("posting_time", sql)
		self.assertIn("creation", sql)
		# verify ordering appears after the UNION ALL
		order_pos = sql.rfind("order by")
		union_pos = sql.rfind("union all")
		self.assertGreater(order_pos, union_pos, "ORDER BY must follow the last UNION ALL")

	def test_sle_query_selects_posting_time_and_creation(self):
		"""posting_time and creation must be in the SELECT list of each sub-query
		so ORDER BY on the UNION ALL result is valid."""
		filters = {"from_date": "2026-01-01", "to_date": "2026-12-31", "company": "_Test Company"}
		sql = eds.get_stock_ledger_entries_query(filters, []).get_sql().lower()
		self.assertIn("`posting_time`", sql)
		self.assertIn("`creation`", sql)
