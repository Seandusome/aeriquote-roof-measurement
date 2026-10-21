const fs=require('fs'),assert=require('assert'),{JSDOM}=require('jsdom');
(async()=>{
const dom=new JSDOM(fs.readFileSync('site/contact-support.html','utf8'),{url:'https://example.com/site/contact-support',runScripts:'outside-only'}),w=dom.window,d=w.document;
assert.equal(d.querySelectorAll('input[name=topic]').length,6);assert.equal(d.querySelectorAll('.support-topic svg').length,6);
let posts=[],fail=true;w.fetch=async(url,options={})=>{
 if(url.endsWith('/config'))return {ok:true,json:async()=>({csrf:'test-csrf'})};
 posts.push(JSON.parse(options.body));assert.equal(options.headers['X-CSRF-Token'],'test-csrf');
 if(fail)throw Error('Network unavailable');return {ok:true,json:async()=>({reference:'AQ-TEST123'})};
};
w.eval(fs.readFileSync('site/support.js','utf8'));
const form=d.getElementById('support-form');form.reportValidity=()=>true;
d.querySelector('[name=topic]').checked=true;
for(const [key,value] of Object.entries({name:'Tester',email:'tester@example.com',message:'Please help with setup.',device:'Mobile phone'}))form.elements.namedItem(key).value=value;
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
form.dispatchEvent(new w.Event('submit',{cancelable:true}));await tick();
assert(d.getElementById('support-status').textContent.includes('Network unavailable'));assert.equal(form.elements.namedItem('message').value,'Please help with setup.');
fail=false;form.dispatchEvent(new w.Event('submit',{cancelable:true}));await tick();
assert.equal(posts[0].request_id,posts[1].request_id);assert(d.getElementById('support-status').textContent.includes('AQ-TEST123'));assert.equal(d.getElementById('support-send').disabled,false);
console.log('PASS six accessible icon topics, form submission, error recovery, duplicate-safe retry and saved reference');dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
