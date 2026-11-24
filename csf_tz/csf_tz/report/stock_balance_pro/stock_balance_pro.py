# Copyright (c) 2013, Aakvatech and contributors
# For license information, please see license.txt

import erpnext
import frappe
from erpnext.stock.utils import add_additional_uom_columns
from frappe import _
from frappe.query_builder import Field

from csf_tz.csf_tz.report.excise_duty_stock.excise_duty_stock import (
	get_item_details,
	get_item_warehouse_map,
	get_items,
	get_stock_ledger_entries_query,
	get_variants_attributes,
)


def execute(filters=None):
	if not filters:
		filters = {}

	validate_filters(filters)

	if filters.get("company"):
		company_currency = erpnext.get_company_currency(filters.get("company"))
	else:
		company_currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	include_uom = filters.get("include_uom")
	columns = get_columns(filters)
	items = get_items(filters)
	sle = get_stock_ledger_entries(filters, items)

	# if no stock ledger entry found return
	if not sle:
		return columns, []

	iwb_map = get_item_warehouse_map(filters, sle)
	item_map = get_item_details(items, sle, filters)

	data = []
	conversion_factors = {}

	def _func(x):
		return x[1]

	for company, item in sorted(iwb_map):
		if item_map.get(item):
			qty_dict = iwb_map[(company, item)]

			report_data = {
				"currency": company_currency,
				"item_code": item,
				"company": company,
			}
			report_data.update(item_map[item])
			report_data.update(qty_dict)

			if include_uom:
				conversion_factors.setdefault(item, item_map[item].conversion_factor)

			data.append(report_data)

	add_additional_uom_columns(columns, data, include_uom, conversion_factors)
	return columns, data


def get_columns(filters):
	"""return columns"""
	columns = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
		{"label": _("Item Name"), "fieldname": "item_name", "width": 150},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 100,
		},
		{
			"label": _("Stock UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 90,
		},
		{
			"label": _("Balance Qty"),
			"fieldname": "bal_qty",
			"fieldtype": "Float",
			"width": 100,
			"convertible": "qty",
		},
		{
			"label": _("Opening Qty"),
			"fieldname": "opening_qty",
			"fieldtype": "Float",
			"width": 100,
			"convertible": "qty",
		},
		{
			"label": _("In Qty"),
			"fieldname": "in_qty",
			"fieldtype": "Float",
			"width": 80,
			"convertible": "qty",
		},
		{
			"label": _("Out Qty"),
			"fieldname": "out_qty",
			"fieldtype": "Float",
			"width": 80,
			"convertible": "qty",
		},
		{
			"label": _("Excise Qty"),
			"fieldname": "excise_stock",
			"fieldtype": "Float",
			"width": 100,
			"convertible": "qty",
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 100,
		},
	]

	if filters.get("show_variant_attributes"):
		columns += [
			{"label": att_name, "fieldname": att_name, "width": 100} for att_name in get_variants_attributes()
		]

	return columns


def get_stock_ledger_entries(filters, items):
	return (
		get_stock_ledger_entries_query(filters, items)
		.orderby(Field("posting_date"))
		.orderby(Field("posting_time"))
		.orderby(Field("creation"))
		.run(as_dict=True)
	)


def validate_filters(filters):
	if not (filters.get("item_code") or filters.get("warehouse")):
		sle_count = frappe.db.count("Stock Ledger Entry")
		if sle_count > 500000:
			frappe.throw(_("Please set filter based on Item or Warehouse due to a large amount of entries."))
