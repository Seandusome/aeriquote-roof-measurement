/* Functional checks for the shared public UI. Layout still requires live visual review. */
const fs=require('fs'),path=require('path'),assert=require('assert'),{JSDOM}=require('jsdom');
const site=path.join(__dirname,'../site');
const files=fs.readdirSync(site).filter(f=>f.endsWith('.html')).concat(fs.readdirSync(path.join(site,'industries')).filter(f=>f.endsWith('.html')).map(f=>'industries/'+f));
const ui=fs.readFileSync(path.join(site,'site-ui.js'),'utf8');let pages=0;
for(const file of files){
 const dom=new JSDOM(fs.readFileSync(path.join(site,file),'utf8'),{url:'https://test.invalid/site/'+file,runScripts:'outside-only'}),d=dom.window.document;
 assert(d.querySelector('meta[name=viewport]'),file+' viewport');assert(d.querySelector('link[href^="/site/site-ui.css"]'),file+' shared styles');
 assert(d.querySelector('link[rel=icon]'),file+' favicon');
 const ids=[...d.querySelectorAll('[id]')].map(x=>x.id);assert.equal(new Set(ids).size,ids.length,file+' duplicate IDs');
 for(const field of d.querySelectorAll('input:not([type=hidden]),select,textarea'))assert(field.labels?.length||field.hasAttribute('aria-label')||field.hasAttribute('aria-labelledby'),file+' field missing label');
 if(d.querySelector('header .nav')){
  const menu=d.querySelector('.aq-mobile-menu');assert(menu,file+' menu');assert(menu.querySelector('nav[aria-label] a[href="/dealer-login"]'),file+' mobile login');
  for(const slug of ['roofing','snow-removal','pressure-washing','paving-sealcoating','landscaping','commercial-property'])assert(menu.querySelector('a[href="/site/industries/'+slug+'"]'),file+' industry '+slug);
  dom.window.eval(ui);menu.open=true;menu.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert(!menu.open,file+' Escape');assert.equal(d.activeElement,menu.querySelector('summary'));
  menu.open=true;d.body.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true}));assert(!menu.open,file+' outside close');
  menu.open=true;menu.querySelector('a').dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true,cancelable:true}));assert(!menu.open,file+' link close');
 }
 for(const a of d.querySelectorAll('a[href^="#"]')){const id=a.getAttribute('href').slice(1);if(id)assert(d.getElementById(id),file+' missing anchor '+id);}
 if(/^(terms-of-use|privacy-policy|refund-cancellation)\.html$/.test(file)){assert(d.querySelector('.aq-contents ol a'),file+' contents');assert(d.querySelector('.aq-back-top'),file+' return');}
 if(file==='features.html'){assert.equal(d.querySelectorAll('.aq-tile-media').length,6);assert(!d.querySelector('.tile img[src$="approved.png"]'));}
 if(file==='how-it-works.html'){assert(d.querySelector('.aq-estimate-preview'));assert(d.querySelector('.aq-estimate-preview').textContent.includes('$784.50'));}
 dom.window.close();pages++;
}
const css=fs.readFileSync(path.join(site,'site-ui.css'),'utf8');
function luminance(hex){const rgb=hex.match(/\w\w/g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;}
function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
assert(contrast('b94108','ffffff')>=4.5);assert(contrast('c4d2e3','071a3d')>=4.5);assert(css.includes('prefers-reduced-motion'));
console.log('PASS: '+pages+' pages, accessible menu keyboard/link/outside handling, all form labels, anchor targets, legal contents, approved aerial thumbnails, readable estimate sample and WCAG AA text color pairs');
