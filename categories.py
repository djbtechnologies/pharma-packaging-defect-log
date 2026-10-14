"""Defect categories, the workbook layout, and the category dropdowns. Shared by build_log.py and analyze.py."""

from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

WORKBOOK = "packaging_defect_log.xlsx"

CATEGORIES = [
    ("Seal or closure failure",
     "The cap, crimp, stopper, plunger seal, port, weld, or seam that closes the package is loose, missing, or leaks."),
    ("Label mix-up or wrong label",
     "A label, carton, overwrap, barcode, or RFID tag is wrong, missing, unreadable, or does not match the product inside."),
    ("Missing or illegible lot or expiry",
     "The lot number, expiration date, or beyond use date is missing, unreadable, or wrong."),
    ("Wrong count or missing units",
     "The pack holds less than stated, such as a short fill, an empty unit, or a missing kit part."),
    ("Foreign material found in packaging",
     "Particles or debris are inside the package, such as glass, rubber stopper pieces, plastic, metal, or hair."),
    ("Container damage or leak",
     "The container body is cracked, broken, has pinholes, or leaks, and no specific seal is named as the cause."),
    ("Package insert error",
     "The package insert or instructions for use is wrong, outdated, missing, or belongs to a different product."),
    ("Other packaging",
     "A packaging problem that fits none of the groups above, such as the wrong component packed in a kit."),
    ("Not packaging (exclude)",
     "The root cause is not packaging, such as temperature exposure, potency, stability, or a formulation error. Left out of the analysis."),
]
CATEGORY_NAMES = [name for name, _ in CATEGORIES]
EXCLUDE = "Not packaging (exclude)"

LOG_COLUMNS = [
    "Recall Number", "Event ID", "Report Date", "Year", "Firm", "Product",
    "Route", "Injectable", "Class", "Status", "Reason for Recall",
    "Defect Category", "Category Rationale", "Reviewed Category",
]


def column_letter(ws, header):
    for cell in ws[1]:
        if cell.value == header:
            return cell.column_letter
    raise KeyError(f"no '{header}' column on {ws.title}")


def add_dropdowns(wb):
    """Category dropdowns on Defect Category and Reviewed Category, fed by the Categories sheet."""
    wb.defined_names["CategoryList"] = DefinedName(
        "CategoryList", attr_text=f"Categories!$A$2:$A${len(CATEGORIES) + 1}")

    ws = wb["Recall Log"]
    ws.data_validations.dataValidation = []  # start clean so reruns don't stack duplicates
    dv = DataValidation(type="list", formula1="=CategoryList", allow_blank=True)
    dv.errorTitle = "Not a category"
    dv.error = "Pick a category from the list. Definitions are on the Categories sheet."
    dv.showErrorMessage = True
    for header in ["Defect Category", "Reviewed Category"]:
        col = column_letter(ws, header)
        dv.add(f"{col}2:{col}{max(ws.max_row, 2)}")
    ws.add_data_validation(dv)
