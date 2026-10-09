from pathlib import Path
p=Path("app.py")
s=p.read_text()
old='def is_head_office():\n    return "head office" in str(session.get("dealer_name") or "").lower()'
new='''def is_head_office():
    if session.get("account_type") != "owner" or not session.get("dealer_id"):
        return False
    con=estimate_db()
    try:
        row=con.execute("SELECT email,status FROM dealers WHERE id=?",(session["dealer_id"],)).fetchone()
        return bool(row and str(row["status"]).lower()=="active" and str(row["email"]).strip().lower()=="sdusome@diitalk.com")
    finally:
        con.close()'''
assert s.count(old)==1, "Head Office definition changed"
s=s.replace(old,new)
p.write_text(s)
