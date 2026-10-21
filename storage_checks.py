"""Head Office checkpoints compare saved records across a service restart."""
import hashlib,hmac,json,os,secrets,uuid
from datetime import datetime
from flask import request,session,Response,render_template_string,redirect
BOOT_ID=uuid.uuid4().hex
TABLES={'dealers':'id','dealer_employees':'id','dealer_profiles':'dealer_id','estimates':'id','estimate_revisions':'revision_id','support_requests':'id'}
def init_storage_db(con):
    con.execute('CREATE TABLE IF NOT EXISTS storage_checkpoints (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, boot_id TEXT NOT NULL, backend TEXT NOT NULL, snapshot TEXT NOT NULL)')
def snapshot(con):
    result={}
    for table,key in TABLES.items():
        result[table]={str(row[key]):hashlib.sha256(json.dumps(dict(row),sort_keys=True,default=str).encode()).hexdigest() for row in con.execute('SELECT * FROM '+table).fetchall()}
    return result
def compare(before,after):
    return {table:{'before':len(before[table]),'now':len(after[table]),'missing':len(set(before[table])-set(after[table])),'changed':sum(after[table].get(k)!=v for k,v in before[table].items() if k in after[table]),'added':len(set(after[table])-set(before[table]))} for table in TABLES}
PAGE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Deployment storage check</title><style>body{font:16px Arial;background:#f4f8fc;color:#173b61;margin:30px auto;padding:0 18px;max-width:1000px;line-height:1.6}section{background:white;padding:22px;border:1px solid #ccd9e5;border-radius:12px;margin:20px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}button{padding:14px;background:#125da8;color:white;border:0;border-radius:8px}a{color:#0757a6}.scroll{overflow:auto}</style></head><body><a href="/head-office/dealers">← Admin Dashboard</a><h1>Deployment storage check</h1><section><b>Connected database: {{backend}}</b><p>{{'PostgreSQL is connected. Verify backup settings separately in Render.' if backend=='PostgreSQL' else 'SQLite is connected. Deployment durability requires a persistent disk; this page cannot verify the Render disk configuration.'}}</p><p>Stable session secret configured: {{'Yes' if secret else 'No — login sessions will reset when the service restarts.'}}</p><p>Save a checkpoint, note its reference, then redeploy and reload this page. This compares accounts, profiles, estimates, revisions and support requests without editing them. A checkpoint is a comparison record, not a backup.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><button>Save pre-deployment checkpoint</button></form></section>{% if checkpoint %}<section><h2>Checkpoint {{checkpoint.id}}</h2><p>Saved {{checkpoint.created_at}} · {{checkpoint.backend}}</p><p><b>{{'A different application process is running.' if restarted else 'Same application process: redeploy, then reload to finish the check.'}}</b> A different process alone does not prove a deployment occurred.</p><div class="scroll"><table><tr><th>Records</th><th>Before</th><th>Now</th><th>Missing</th><th>Changed</th><th>Added</th></tr>{% for name,r in results.items() %}<tr><th>{{name}}</th><td>{{r.before}}</td><td>{{r.now}}</td><td>{{r.missing}}</td><td>{{r.changed}}</td><td>{{r.added}}</td></tr>{% endfor %}</table></div><p>Missing records need investigation. Changed records can reflect normal activity; additions are expected as customers use AeriQuote. If this checkpoint disappears after deployment, do not treat persistence as verified.</p></section>{% else %}<section>No checkpoint found. Save one before the next deployment.</section>{% endif %}</body></html>'''
def register_storage(app,estimate_db,is_head_office):
    @app.route('/head-office/storage',methods=['GET','POST'])
    def storage_check():
        if not is_head_office():return Response('Head Office permission required.',status=403)
        session.setdefault('storage_csrf',secrets.token_urlsafe(32))
        con=estimate_db()
        try:
            backend='PostgreSQL' if con.postgres else 'SQLite'
            if request.method=='POST':
                if not hmac.compare_digest(str(request.form.get('csrf') or ''),session['storage_csrf']):return Response('Refresh and try again.',status=400)
                con.execute('INSERT INTO storage_checkpoints(id,created_at,boot_id,backend,snapshot) VALUES(?,?,?,?,?)',(uuid.uuid4().hex[:12],datetime.utcnow().isoformat()+'Z',BOOT_ID,backend,json.dumps(snapshot(con))))
                con.commit();return redirect('/head-office/storage')
            checkpoint=con.execute('SELECT * FROM storage_checkpoints ORDER BY created_at DESC LIMIT 1').fetchone()
            results=compare(json.loads(checkpoint['snapshot']),snapshot(con)) if checkpoint else None
            response=Response(render_template_string(PAGE,backend=backend,secret=bool(os.environ.get('FLASK_SECRET_KEY')),checkpoint=checkpoint,results=results,restarted=bool(checkpoint and checkpoint['boot_id']!=BOOT_ID),csrf=session['storage_csrf']),content_type='text/html')
            response.headers['Cache-Control']='no-store';return response
        finally:con.close()
