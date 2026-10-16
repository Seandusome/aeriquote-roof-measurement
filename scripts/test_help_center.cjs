const fs=require('fs'),assert=require('assert/strict'),{JSDOM}=require('jsdom'),{execFileSync}=require('child_process');
const js=fs.readFileSync('site/help-center.js','utf8');
(async()=>{
const page=new JSDOM(fs.readFileSync('site/help.html','utf8'),{url:'https://example.com/site/help',runScripts:'outside-only'}),w=page.window,d=w.document;w.eval(js);
const articles=[...d.querySelectorAll('.aq-help-article')];assert.equal(articles.length,6);assert(d.body.textContent.includes('2301 Ave C North #115'));
const search=d.getElementById('aq-help-search');search.value='password';search.dispatchEvent(new w.Event('input'));assert.equal(articles.filter(x=>!x.hidden).length,1);assert.equal(d.querySelector('.aq-help-article:not([hidden])').id,'account-access');
search.value='zzzz-no-match';search.dispatchEvent(new w.Event('input'));assert.equal(d.getElementById('aq-help-empty').hidden,false);
w.location.hash='pdf-history';await new Promise(r=>setTimeout(r,15));assert.equal(search.value,'');assert(d.getElementById('pdf-history').open);assert.equal(articles.filter(x=>!x.hidden).length,6);
const select=d.getElementById('aq-guide-industry');for(const industry of ['roofing','snow','pressure','paving','landscaping','commercial']){select.value=industry;select.dispatchEvent(new w.Event('change'));assert(d.getElementById('aq-guide-industry-tip').textContent.length>40);}
page.window.close();
// Render the real app markup, but do not run the measurement engine in this test.
const html=execFileSync('python',['-c',"import ast,pathlib; tree=ast.parse(pathlib.Path('app.py').read_text()); print(next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HTML' for t in n.targets)))"],{maxBuffer:4000000}).toString();
const app=new JSDOM(html,{url:'https://example.com/',runScripts:'outside-only'}),a=app.window,ad=a.document;let calls=0;a.fetch=()=>{calls++;throw Error('Help must not request billable or job data')};
ad.getElementById('streetAddress').value='Existing job address';ad.getElementById('businessType').value='landscaping';a.eval(js);
const launch=ad.querySelector('[data-aq-help-topic="first-estimate"]'),dialog=ad.querySelector('.aq-help-dialog');assert(!dialog.open);assert.equal(ad.querySelectorAll('[data-aq-help-topic]').length,6);
launch.click();assert(dialog.open);assert(dialog.textContent.includes('Guide step 1 of 5'));assert.equal(ad.activeElement.id,'aq-help-close');
for(let n=1;n<5;n++){ad.getElementById('aq-help-next').click();assert(dialog.textContent.includes('Guide step '+(n+1)+' of 5'));}
ad.getElementById('aq-help-next').click();assert(!dialog.open);assert.equal(ad.activeElement,launch);
ad.querySelector('[data-aq-help-topic="measure"]').click();assert(dialog.textContent.includes('Landscaping:'));assert(dialog.querySelector('.aq-help-nav').hidden);
dialog.dispatchEvent(new a.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert(!dialog.open);
ad.getElementById('businessType').value='snow';ad.querySelector('[data-aq-help-topic="measure"]').click();assert(dialog.textContent.includes('Snow Removal:'));assert(!/roof|garage|pitch|shingle/i.test(ad.getElementById('aq-help-dialog-lines').textContent));ad.getElementById('aq-help-close').click();ad.getElementById('businessType').value='landscaping';
ad.querySelector('[data-aq-help-topic="price"]').click();const last=ad.querySelector('#aq-help-full').parentNode.querySelector('a:last-child');last.focus();dialog.dispatchEvent(new a.KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));assert.equal(ad.activeElement.id,'aq-help-close');ad.getElementById('aq-help-close').click();
assert.equal(ad.getElementById('streetAddress').value,'Existing job address');assert.equal(ad.getElementById('businessType').value,'landscaping');assert.equal(calls,0);
assert(!ad.querySelector('#toolAiBtn'));app.window.close();
console.log('PASS six searchable guides, deep links, all industry variants, optional five-step guide, keyboard focus/close and no job mutation or API calls');
})().catch(e=>{console.error(e);process.exit(1)});
