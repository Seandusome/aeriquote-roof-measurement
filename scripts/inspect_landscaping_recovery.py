from pathlib import Path
s=Path("app.py").read_text()
for term in ("function commercialActive(", "function commercialAreaUi(", "function commercialAddArea(", "function priceCalc(", "function captureQuoteSnapshot(", "async function buildInteractiveCustomerMap(", "function showCustomerEstimate("):
    i=s.find(term)
    print("\n=== "+term+" at "+str(i)+" ===")
    print(s[i:i+2800] if i>=0 else "MISSING")
