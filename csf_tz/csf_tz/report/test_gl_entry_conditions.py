"""Offline tests for gl_entry_conditions helpers."""

import unittest

from csf_tz.csf_tz.report.gl_entry_conditions import normalize_filter_list


class TestNormalizeFilterList(unittest.TestCase):
	"""normalize_filter_list must accept a list, a JSON list or a plain name."""

	def test_plain_string_wrapped_in_list(self):
		"""A plain cost-center name must become ['Main - BML'], not ['M','a','i',…]."""
		result = normalize_filter_list("Main - BML")
		self.assertEqual(result, ["Main - BML"])

	def test_json_encoded_list_decoded(self):
		"""A JSON-encoded list as sent by the form widget must be decoded."""
		result = normalize_filter_list('["Main - BML", "Branch - BML"]')
		self.assertEqual(result, ["Main - BML", "Branch - BML"])

	def test_already_a_list_returned_as_list(self):
		"""A Python list must pass through unchanged."""
		result = normalize_filter_list(["Main - BML"])
		self.assertEqual(result, ["Main - BML"])

	def test_already_a_tuple_returned_as_list(self):
		"""A tuple must be converted to a list."""
		result = normalize_filter_list(("Main - BML",))
		self.assertEqual(result, ["Main - BML"])

	def test_json_encoded_single_string_wrapped(self):
		"""A JSON-encoded plain string (rare but possible) must become a single-item list."""
		result = normalize_filter_list('"Main - BML"')
		self.assertEqual(result, ["Main - BML"])
