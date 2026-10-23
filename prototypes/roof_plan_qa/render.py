"""Local QA artifact generator. No application routes, customer data, network or storage writes."""
import sys,math,json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,Color,white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from model import load,validate,quantities,price,ROOT
REPO=ROOT.parents[1]
NAVY=HexColor('#15344f');BLUE=HexColor('#236697');MUTED=HexColor('#536b7f');LINE=HexColor('#ccdbe7');PALE=HexColor('#f1f6fa')
COLORS=[HexColor('#a9c9e4'),HexColor('#dcebf6'),HexColor('#9ecbc7'),HexColor('#d9ece9')]

def make_pdf(data,out):
    validate(data);q=quantities(data);pr=price(data)
    pdfmetrics.registerFont(TTFont('AQ',str(REPO/'qa_assets/DejaVuSans.ttf')));pdfmetrics.registerFont(TTFont('AQB',str(REPO/'qa_assets/DejaVuSans-Bold.ttf')))
    c=canvas.Canvas(str(out),pagesize=(612,792));c.setTitle('AeriQuote | Fictional QA Roof-Plan Estimate')
    def txt(s,x,y,size=9,bold=False,color=NAVY):
        c.setFillColor(color);c.setFont('AQB' if bold else 'AQ',size);c.drawString(x,y,str(s))
    def rule(y):c.setStrokeColor(LINE);c.setLineWidth(.6);c.line(38,y,574,y)
    def box(x,y,w,h,color=PALE):c.setFillColor(color);c.rect(x,y,w,h,fill=1,stroke=0)
    def header(page):
        c.drawImage(str(REPO/'site/assets/aeriquote-logo.png'),38,724,width=92,height=38,preserveAspectRatio=True,mask='auto')
        txt('AeriQuote Demo',145,749,17,True);txt('ROOF MEASUREMENTS & BRANDED ESTIMATES',145,733,7,color=BLUE)
        txt('(306) 555-0100',438,753,8);txt('demo@example.invalid',438,740,8);txt('aeriquote.com',438,727,8)
        rule(714);box(38,689,536,17,HexColor('#e8f0f6'));txt('FICTIONAL QA DATA  |  NOT A REAL PROPERTY OR CUSTOMER QUOTE',47,695,7.5,True)
        rule(38);txt('AeriQuote Demo  |  Isolated roof-plan prototype',38,24,7,color=MUTED);txt(f'{page} / 2  |  FICTIONAL QA',464,24,7,color=MUTED)
    def path(points,fill,stroke=NAVY):
        p=c.beginPath();p.moveTo(*points[0]);[p.lineTo(*v) for v in points[1:]];p.close();c.setFillColor(fill);c.setStrokeColor(stroke);c.setLineWidth(1);c.drawPath(p,fill=1,stroke=1)
    def dim(a,b,label,offset):
        dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);nx,ny=-dy/L,dx/L
        aa=[a[0]+nx*offset,a[1]+ny*offset];bb=[b[0]+nx*offset,b[1]+ny*offset]
        c.setStrokeColor(MUTED);c.setLineWidth(.45);c.line(*a,*aa);c.line(*b,*bb);c.line(*aa,*bb)
        for p,sg in [(aa,1),(bb,-1)]:
            ux,uy=dx/L*sg,dy/L*sg;c.line(*p,p[0]+ux*4+nx*1.5,p[1]+uy*4+ny*1.5);c.line(*p,p[0]+ux*4-nx*1.5,p[1]+uy*4-ny*1.5)
        tw=pdfmetrics.stringWidth(label,'AQ',8);mx,my=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2;box(mx-tw/2-2,my-3,tw+4,10,white);txt(label,mx-tw/2,my,8)
    def plan(building,x,y,scale,detail=False):
        L,W=building['length'],building['width'];idx=0 if building['id']=='A' else 2
        xy=lambda v:(x+v[0]*scale,y+v[1]*scale)
        for i,p in enumerate(building['planes']):
            path([xy(v) for v in p['vertices']],COLORS[idx+i]);cx=x+L*scale/2;cy=y+(W/4 if i==0 else W*3/4)*scale
            label=p['id'];sz=10 if detail else 11;tw=pdfmetrics.stringWidth(label,'AQB',sz);box(cx-tw/2-5,cy-5,tw+10,17,NAVY);txt(label,cx-tw/2,cy,sz,True,white)
            # Slope direction follows the explicitly defined plane heights.
            ax=x+L*scale*.78;start=y+W*scale/2;end=y+(W*.18 if i==0 else W*.82)*scale
            c.setStrokeColor(BLUE);c.setLineWidth(.7);c.line(ax,start+(end-start)*.2,ax,end);c.line(ax,end,ax-3,end+(3 if i==0 else -3));c.line(ax,end,ax+3,end+(3 if i==0 else -3))
        a,b=map(xy,building['ridge']['points']);c.setStrokeColor(NAVY);c.setLineWidth(2);c.line(*a,*b)
        label=building['ridge']['id']+'  CONFIRMED RIDGE';tw=pdfmetrics.stringWidth(label,'AQB',7);box(x+5,y+W*scale/2+2,tw+6,12,white);txt(label,x+8,y+W*scale/2+5,7,True)
        if detail:
            dim((x,y),(x+L*scale,y),f'{L:.2f} ft',-16);dim((x,y),(x,y+W*scale),f'{W:.2f} ft',18)
    def form(b,x,y,w,h):
        project=lambda v:(.866025403784*v[0]-.5*v[1],.353553390593*v[0]+.612372435696*v[1]+.707106781187*v[2])
        projected=[project(v) for p in b['planes'] for v in p['vertices']];xmin=min(p[0] for p in projected);ymin=min(p[1] for p in projected);dx=max(p[0] for p in projected)-xmin;dy=max(p[1] for p in projected)-ymin;s=min(w/dx,h/dy)
        cv=lambda v:(x+(w-dx*s)/2+(project(v)[0]-xmin)*s,y+(h-dy*s)/2+(project(v)[1]-ymin)*s)
        idx=0 if b['id']=='A' else 2
        for i,p in enumerate(b['planes']):path([cv(v) for v in p['vertices']],COLORS[idx+i])
        a,z=map(cv,b['ridge']['points']);c.setLineWidth(2);c.line(*a,*z)
    def table(headers,rows,x,top,widths,row_h=18):
        box(x,top-row_h,sum(widths),row_h,HexColor('#e5eef5'));xx=x
        for label,w in zip(headers,widths):txt(label,xx+7,top-row_h+6,8,True);xx+=w
        y=top-row_h
        for row in rows:
            y-=row_h;xx=x
            for val,w in zip(row,widths):txt(val,xx+7,y+6,8.5);xx+=w
            c.setStrokeColor(LINE);c.setLineWidth(.4);c.line(x,y,x+sum(widths),y)
        return y
    header(1);txt('Property Measurement Overview',38,665,20,True)
    txt('PREPARED FOR',38,638,7.5,color=MUTED);txt('Fictional QA Customer',38,621,10);txt('Test property - no geographic address',38,606,8.5)
    txt('ESTIMATE',395,638,7.5,color=MUTED);txt('QA-GABLE-001  |  CAD',395,621,9);txt('October 22, 2026',395,606,8.5)
    rule(593);txt('Confirmed roof plan',38,574,13,True);txt('Four defined planes. Two explicit ridges. North up in the plan view.',38,560,8.5,color=MUTED)
    box(38,333,536,215);scale=6;plan(data['buildings'][0],67,350,scale);plan(data['buildings'][1],67+55*scale,350+8*scale,scale)
    txt('A  MAIN HOUSE',67,539,8,True);txt('B  DETACHED GARAGE',397,539,8,True)
    txt('N',554,532,9,True);c.setStrokeColor(NAVY);c.setLineWidth(1.1);c.line(558,508,558,525);c.line(558,525,554,519);c.line(558,525,562,519)
    txt('Common plan scale; relative positions use the explicit fictional coordinates.',38,320,8,color=MUTED)
    rows=[]
    for b in data['buildings']:
        planes=[p for p in q if p['building_id']==b['id']];rows.append([b['name'],f"{sum(p['surface_area'] for p in planes):,.2f} ft²",f"{b['planes'][0]['pitch_rise']}/12 confirmed",f"{b['length']:.2f} ft"])
    table(['BUILDING','ROOF SURFACE AREA','PITCH','RIDGE LENGTH'],rows,38,307,[164,143,134,95],21)
    txt('Roof form from the same defined planes',38,224,12,True);txt('Orthographic views; heights are specified relative to each building’s eaves.',38,210,8,color=MUTED)
    box(38,72,259,126);box(309,72,265,126);form(data['buildings'][0],51,91,232,93);form(data['buildings'][1],326,91,230,93)
    txt('MAIN HOUSE  |  RIDGE RISE 7.50 ft',51,80,8,True);txt('GARAGE  |  RIDGE RISE 3.33 ft',322,80,8,True)
    txt('Roof-only illustration. No walls, dormers, hips or valleys have been added.',38,55,8,color=MUTED)
    c.showPage();header(2);txt('Measurements & Customer Estimate',38,665,18,True);txt('Fictional QA Customer  |  QA-GABLE-001  |  CAD  |  October 22, 2026',38,646,8.5,color=MUTED)
    for b,x,s in [(data['buildings'][0],38,4),(data['buildings'][1],312,6)]:
        box(x,419,262,214);txt(b['id']+'  '+b['name'],x+12,615,11,True);plan(b,x+56,460,s,True)
        txt(f"Pitch {b['planes'][0]['pitch_rise']}/12  |  Ridge {b['length']:.2f} ft",x+12,432,8)
    txt('Roof plane measurements',38,400,12,True)
    schedule=[[p['id']+'  '+p['building'],f"{p['pitch_rise']}/12 ({p['pitch_degrees']:.2f}°)",f"{p['plan_area']:,.2f} ft²",f"{p['surface_area']:,.2f} ft²"] for p in q]
    table(['PLANE / BUILDING','CONFIRMED PITCH','PLAN AREA','SURFACE AREA'],schedule,38,388,[188,141,102,105],18)
    txt('Plane runs: main 15.00 ft horizontal / 16.77 ft sloped; garage 10.00 ft horizontal / 10.54 ft sloped.',38,287,7.5,color=MUTED)
    txt('Estimate summary',38,270,13,True)
    rows=[(name+f' - {qty:,.2f} ft² × CAD {data["rate_cad"]}/ft²',amount) for name,qty,amount in pr['lines']]+[('Subtotal',pr['subtotal']),('GST ('+data['gst_percent']+'%)',pr['gst']),('PST ('+data['pst_percent']+'%)',pr['pst'])]
    y=253
    for label,amount in rows:
        txt(label,45,y,9);c.setFont('AQ',9);c.setFillColor(NAVY);c.drawRightString(566,y,f'CAD {amount:,.2f}');rule(y-7);y-=22
    box(38,y-9,536,28,NAVY);txt('TOTAL (CAD)',46,y+1,11,True,white);c.setFont('AQB',12);c.setFillColor(white);c.drawRightString(566,y,f'CAD {pr["total"]:,.2f}')
    txt('Total roof surface area: '+f'{sum(p["surface_area"] for p in q):,.2f} ft²',38,113,9,True)
    txt('Dimensions are horizontal plan lengths; surface areas include each confirmed pitch.',38,94,8)
    txt('Fictional geometry and simulated confirmations. Not a survey or a real customer estimate.',38,80,8)
    txt('Totals use unrounded plane areas; displayed quantities are rounded.',38,69,7.5,color=MUTED)
    txt('Questions?  (306) 555-0100  |  demo@example.invalid',38,59,8.5)
    c.save()

if __name__=='__main__':
    output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True);data=load();make_pdf(data,output/'AeriQuote_Fictional_Roof_Plan.pdf');print(json.dumps({'planes':[{k:p[k] for k in ['id','plan_area','surface_area','pitch_degrees']} for p in quantities(data)],'pricing':price(data)},default=str,indent=2))
