"""Regression checks for AeriQuote landscaping multi-area recovery.

Run: python scripts/check_landscaping_multi_area.py
These checks are deliberately strict: a passing Python compile is not enough.
"""
from pathlib import Path
import re
import sys

source = Path("app.py").read_text(encoding="utf-8")
checks = {
    "saved independent service area collection": r"\b(?:commercialAreas|savedServiceAreas)\s*=\s*\[",
    "total across all saved areas": r"function\s+(?:multiAreaTotal|savedAreaTotal)\s*\(",
    "create another service area": r"function\s+(?:commercialAddArea|addNewServiceArea)\s*\(",
    "edit existing service area": r"function\s+(?:commercialEditArea|editSavedServiceArea)\s*\(",
    "remove existing service area": r"function\s+(?:commercialRemoveArea|removeSavedServiceArea)\s*\(",
    "persist areas in estimate snapshot": r"(?:serviceAreas|commercialAreas)\s*:\s*(?:clone\(|commercialAreas)",
}
failures = []
for label, pattern in checks.items():
    found = bool(re.search(pattern, source))
    print(f"{'PASS' if found else 'FAIL'}: {label}")
    if not found:
        failures.append(label)

# Prevent a cosmetic multi-area UI from passing without a multi-area price calculation.
calc = re.search(r"function\s+priceCalc\s*\(\)\s*\{(.{0,7000}?)\}\s*\n", source, re.S)
if not calc or not re.search(r"multiAreaTotal|savedAreaTotal|commercialAreas|savedServiceAreas", calc.group(1)):
    failures.append("priceCalc includes all saved service areas")
    print("FAIL: priceCalc includes all saved service areas")
else:
    print("PASS: priceCalc includes all saved service areas")

print(f"\n{len(failures)} outstanding multi-area recovery checks")
sys.exit(1 if failures else 0)
