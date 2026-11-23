// Actual local Streamlit UI + synthetic model/search, never a live API/Safari claim.
const {chromium}=require('playwright'),assert=require('assert/strict');
const latest=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning')}
async function send(p,t){await idle(p);const id=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await p.getByRole('textbox',{name:'질문을 적어주세요'}).fill(t);await p.getByRole('textbox',{name:'질문을 적어주세요'}).press('Enter');await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,id);await idle(p)}
async function tap(p,name){await idle(p);const id=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await p.getByRole('button',{name,exact:true}).tap();await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,id);await idle(p)}
async function choose(p,label,value){const box=p.getByRole('dialog').getByRole('combobox',{name:label,exact:true});await box.click();await box.fill(value);await p.getByRole('option',{name:value,exact:true}).click();}
async function check(p){assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const bad=await p.locator('.stButton button,.stLinkButton a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&(e.getBoundingClientRect().width<43||e.getBoundingClientRect().height<43)).map(e=>e.innerText));assert.deepEqual(bad,[])}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of [320,390,430,768])for(const mode of ['basic','generated']){
 const p=await b.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true,colorScheme:mode==='generated'?'dark':'light'});
 try{
 await p.goto('http://127.0.0.1:'+(mode==='basic'?18527:18529));await p.getByRole('button',{name:/취미 배우기/}).waitFor();await idle(p);
 const grid=p.locator('.st-key-interest_grid_start_interest_ button');assert.equal(await grid.count(),4);const boxes=await Promise.all((await grid.all()).map(e=>e.boundingBox()));assert.ok(Math.abs(boxes[0].y-boxes[1].y)<3);assert.ok(boxes[2].y>boxes[0].y);
 await p.getByRole('button',{name:/취미 배우기/}).click();await p.getByRole('button',{name:'추천받기',exact:true}).waitFor();assert.equal(await p.getByRole('button',{name:'지역 선택하기',exact:true}).count(),0);
 await tap(p,'추천받기');
 if(mode==='basic'){assert.match(await latest(p).innerText(),/AI와 연결되지 않아|기본 탐색/);assert.ok(await p.getByRole('button',{name:/알아보기/}).count());}
 else{
  await send(p,'요즘 심심해');assert.match(await latest(p).innerText(),/마음을 환기/);assert.equal(await latest(p).locator('[class*=st-key-web_card_]').count(),0);
  await send(p,'사람들 만나고 싶어');assert.match(await latest(p).innerText(),/합창이나 춤/);await send(p,'춤은 잘 못 춰');assert.match(await latest(p).innerText(),/입문 동작/);await send(p,'좋아. 근처에 있어?');assert.match(await latest(p).innerText(),/어느 동네/);
 }
 if(mode==='basic')await send(p,'수영 배우고 싶어요');
 await p.getByRole('button',{name:'지역 선택하기',exact:true}).click();await p.getByRole('dialog').waitFor();await choose(p,'시·도','경기도');await choose(p,'시·군·구','화성시 동탄구');await p.getByRole('dialog').getByRole('combobox',{name:'읍·면·동'}).waitFor();
 await p.getByRole('button',{name:'닫기',exact:true}).click();await p.getByRole('dialog').waitFor({state:'hidden'});assert.equal(await latest(p).getByText(/화성시 동탄구/).count(),0);
 await p.getByRole('button',{name:'지역 선택하기',exact:true}).click();await p.getByRole('dialog').waitFor();await p.mouse.click(3,100);await p.getByRole('dialog').waitFor({state:'hidden'});await idle(p);assert.equal(await p.getByRole('dialog').count(),0);
 await p.getByRole('button',{name:'지역 선택하기',exact:true}).click();await choose(p,'시·도','부산광역시');await choose(p,'시·군·구','해운대구');await choose(p,'읍·면·동','우1동');await p.getByRole('dialog').waitFor({state:'hidden'});await latest(p).getByText(/찾는 지역 · 부산광역시 해운대구 우1동/).waitFor();await p.waitForFunction(()=>{const a=[...document.querySelectorAll('[id^=latest-reply-]')].at(-1);return a&&a.getBoundingClientRect().top>=0&&a.getBoundingClientRect().top<220});
 assert.equal(await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).count(),0);
 await p.getByRole('button',{name:'글자 크기',exact:true}).click();await p.getByRole('dialog').waitFor();await p.locator('.st-key-font_choice_2 button').click();await p.getByRole('dialog').waitFor({state:'hidden'});await p.waitForFunction(()=>getComputedStyle(document.querySelector('.stChatInput textarea')).fontSize==='22px');await check(p);
 if(mode==='generated'){
  await send(p,'혼자 집에서 할 수 있는 취미는?');assert.match(await latest(p).innerText(),/사진에 짧은 글/);assert.equal(await latest(p).locator('[class*=st-key-web_card_]').count(),0);await send(p,'연결실패 취미 추천');assert.match(await latest(p).innerText(),/AI와 연결되지 않아|기본 탐색/);
  await send(p,'서울 강서구 화곡동 수영 찾아줘');await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();await tap(p,'자세히 보기');assert.equal(await latest(p).getByRole('link',{name:'전화하기 · 02-0000-0000'}).getAttribute('href'),'tel:0200000000');assert.equal(await latest(p).getByRole('link',{name:'공식 신청 페이지',exact:true}).count(),1);
  await send(p,'그건 너무 비싸');await latest(p).getByText(/금액/).waitFor();await tap(p,'무료로 찾아주세요');await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();await send(p,'다른 거 없을까?');assert.equal(await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).count(),0);await send(p,'혼자 집에서 할 수 있는 취미는?');assert.match(await latest(p).innerText(),/사진에 짧은 글/);assert.equal(await latest(p).locator('[class*=st-key-web_card_]').count(),0);
 }
 await check(p);const roles=await p.locator('[data-ieum-role]').evaluateAll(es=>es.map(e=>({role:e.dataset.ieumRole,text:e.textContent})));assert.ok(roles.some(x=>x.role==='user'&&x.text==='나'));assert.ok(roles.some(x=>x.role==='assistant'&&x.text==='이음 AI'));const bubbles=await p.evaluate(()=>{const u=[...document.querySelectorAll('[data-ieum-role=user]')].at(-1).closest('[data-testid=stChatMessageContent]');const a=[...document.querySelectorAll('[class*=st-key-assistant_bubble_]')].at(-1);return {ux:u.getBoundingClientRect().x,ax:a.getBoundingClientRect().x,user:getComputedStyle(u).backgroundColor,ai:getComputedStyle(a).backgroundColor}});assert.ok(bubbles.ux>bubbles.ax);assert.notEqual(bubbles.user,bubbles.ai);await p.screenshot({path:`/workspace/work/national-browser/${width}-${mode}.png`});console.log('PASS national modal/context/free-prose/basic-failure/choices/font/layout',width,mode);
 }catch(e){await p.screenshot({path:`/workspace/work/national-browser/failure-${width}-${mode}.png`,fullPage:true});throw e}finally{await p.close()}
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
