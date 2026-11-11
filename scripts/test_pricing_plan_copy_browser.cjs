const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
const output=process.env.QA_PRICING_OUTPUT||'/tmp/aq-pricing-review';fs.mkdirSync(output,{recursive:true});
const explanation='Load the property, trace the roof and confirm pitch. Apply your pricing and save a branded estimate. Measure areas and lengths for other services.';
(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.QA_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});const results=[];
try{for(const width of [1440,390]){
 const c=await b.newContext({viewport:{width,height:900}}),p=await c.newPage(),errors=[],payments=[];p.on('pageerror',e=>errors.push(e.message));await c.route('**/*',r=>{if(new URL(r.request().url()).hostname!=='127.0.0.1'){payments.push(r.request().url().split('/')[2]);return r.abort()}return r.continue()});
 for(const [route,kind,grid] of [['pricing','pricing','.plan-grid'],['upgrade?plan=pro','upgrade','.plans'],['','home','.price-grid']]){
  await p.goto('http://127.0.0.1:8765/site/'+route);assert.equal(await p.evaluate(()=>innerWidth),width);
  const cards=p.locator(grid+(kind==='home'?' article':' .plan'));assert.equal(await cards.count(),3);
  for(const [i,name,price,quantity] of [[0,'Basic',29,25],[1,'Pro',59,75],[2,'Business',99,200]]){
   const card=cards.nth(i),text=await card.innerText();assert(text.includes(name));assert(text.includes('$'+price));assert(text.includes(quantity+' '+(kind==='pricing'?'property measurements':'measurements')));assert(text.includes('Aerial roof tracing with pitch confirmation'));assert(text.includes('Branded PDF estimates'));assert(text.includes(quantity+' customer estimates / month'));assert(await card.isVisible());
  }
  if(kind==='pricing'){for(const label of ['Area and linear measurement tools','Employee logins — shared business allowance']){const row=p.getByRole('row').filter({hasText:label});assert.equal(await row.getByRole('cell',{name:'✓',exact:true}).count(),3)}assert.equal(await p.getByRole('row').filter({hasText:'Business dashboard / usage'}).count(),0);await p.locator('.compare table').screenshot({path:`${output}/comparison-${width}.png`})}
  const help=p.getByText(explanation,{exact:true});assert.equal(await help.count(),1);assert(await help.isVisible());assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No page overflow');
  if(kind==='upgrade')assert(await cards.first().locator('small').evaluate(e=>parseFloat(getComputedStyle(e).fontSize)>=14));
  await p.locator('h1').click();
  await p.screenshot({path:`${output}/${kind}-page-${width}.png`,fullPage:true});
  if((await p.locator(grid).boundingBox()).height<=900)await p.locator(grid).screenshot({path:`${output}/${kind}-cards-${width}.png`});await help.screenshot({path:`${output}/${kind}-explanation-${width}.png`});
  if(kind==='upgrade'){for(const name of ['basic','pro','business']){await p.locator('[data-plan="'+name+'"]').click();assert.equal(await p.locator('[data-plan="'+name+'"]').getAttribute('aria-pressed'),'true')}assert((await p.locator('.notice').innerText()).includes('Checkout is not yet enabled'));assert.equal(await p.locator('input[type=number],input[name=cardnumber],iframe').count(),0)}
  results.push({width,actualWidth:await p.evaluate(()=>innerWidth),page:kind,cards:3,wording:'pass',allowances:'25/75/200',brandedEstimates:'pass',explanation:'pass',overflow:'none',browser:b.version()});
 }
 assert.deepEqual(errors,[]);assert.equal(payments.length,0);await c.close();
}}finally{await b.close()}fs.writeFileSync(output+'/results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2))})().catch(e=>{console.error(e);process.exitCode=1});
