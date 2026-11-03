import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ReboundConfiguration(Document):
	def validate(self):
		for field in ("block_length_inches", "block_width_inches", "block_height_inches"):
			if flt(self.get(field)) < 0:
				frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(field)))

		if self.target_block_item and any(
			flt(self.get(f"block_{dim}_inches")) > 0 for dim in ("length", "width", "height")
		):
			item = frappe.db.get_value(
				"Item",
				self.target_block_item,
				["custom_length", "custom_width", "custom_height"],
				as_dict=True,
			)
			if not item:
				return
			# Soft warning only in error log if block item dims differ from profile
			for profile_field, item_field in (
				("block_length_inches", "custom_length"),
				("block_width_inches", "custom_width"),
				("block_height_inches", "custom_height"),
			):
				p = flt(self.get(profile_field))
				i = flt(item.get(item_field))
				if p > 0 and i > 0 and abs(p - i) > 0.01:
					frappe.msgprint(
						_(
							"Block profile dimensions differ from Target Block Item {0} ({1}). "
							"Production entry defaults use the profile."
						).format(self.target_block_item, item_field),
						indicator="orange",
					)
					break
