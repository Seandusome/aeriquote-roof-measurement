"""Disposable loopback existing-job fixture using normal paid allowance rules."""
import fresh_user_browser_server as fixture

a=fixture.a
con=fixture.disposable_db()
con.execute("UPDATE dealers SET plan_code='basic',lookup_limit=25,estimate_limit=25 WHERE id='qa-browser'")
con.execute("UPDATE account_allowances SET complimentary=0 WHERE dealer_id='qa-browser'")
con.commit();con.close()
if __name__=='__main__':a.app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)
