// Local Chromium + synthetic HTTP/Gemini failure fixtures; not Safari/live APIs.
const {chromium}=require('playwright');const assert=require('assert/strict');
const latest=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning')}
async function send(p,text){await idle(p);let id=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await p.getByRole('textbox',{name:'질문을 적어주세요'}).fill(text);await p.getByRole('textbox',{name:'질문을 적어주세요'}).press('Enter');await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,id);await idle(p)}
async function tap(p,name){await idle(p);let id=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await p.getByRole('button',{name,exact:true}).tap();await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,id);await idle(p)}
async function layout(p){assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const bad=await p.locator('.stButton button,.stLinkButton a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&(e.getBoundingClientRect().height<43||e.getBoundingClientRect().width<43)).map(e=>e.innerText));assert.deepEqual(bad,[])}
async function fresh(p,url){await p.goto(url);await p.getByRole('button',{name:/운동하기/}).waitFor();await idle(p)}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of [320,390,430,768])for(const mode of ['keyless','mock']){
 const p=await b.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true,colorScheme:mode==='mock'?'dark':'light'});
 try{
 await fresh(p,'http://127.0.0.1:'+(mode==='mock'?18528:18527));assert.equal(await p.getByRole('button',{name:/서울 강서구/}).count(),0);assert.ok(!(await p.locator('[data-testid=stChatMessage]').innerText()).includes('Gemini'));
 await send(p,'안녕하세요');assert.match(await latest(p).innerText(),/안녕하세요/);assert.equal(await latest(p).locator('[class*=st-key-web_card_]').count(),0);
 await send(p,'요즘 심심해요');await p.getByRole('button',{name:'그림·만들기 알아보기',exact:true}).waitFor();assert.match(await latest(p).innerText(),/일반 활동/);await layout(p);
 await send(p,'그림을 처음 배우려면?');assert.match(await latest(p).innerText(),/연필과 종이/);assert.equal(await latest(p).locator('[class*=st-key-web_card_]').count(),0);
 await tap(p,'근처에서 배울 곳 찾기');assert.match(await latest(p).innerText(),/어느 동네/);assert.equal(await p.getByRole('button',{name:'서울 강서구',exact:true}).count(),0);
 await send(p,'인천에 살아요');assert.doesNotMatch(await latest(p).innerText(),/효도아쿠아|파크골프|슬로우조깅/);
 await send(p,'부천 중동에서 수영 배우고 싶어요');assert.doesNotMatch(await latest(p).innerText(),/어느 구|어느 동네에서 찾아볼까요|강서구/);
 await send(p,'수영 배우고 싶어요');assert.doesNotMatch(await latest(p).innerText(),/어느 동네에서 찾아볼까요/);
 await send(p,'너무 비싸요');assert.match(await latest(p).innerText(),/금액/);await tap(p,'무료로 찾아주세요');await send(p,'너무 멀어요');assert.match(await latest(p).innerText(),/어느 동네를 기준/);
 await send(p,'처음부터');await p.getByRole('button',{name:/운동하기/}).waitFor();await send(p,'수영 배우고 싶어요');assert.match(await latest(p).innerText(),/어느 동네/);
 await send(p,'서울 강서구 화곡동이에요');
 if(mode==='mock'){
  await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();await tap(p,'자세히 보기');assert.equal(await latest(p).getByRole('link',{name:'전화하기 · 02-0000-0000'}).getAttribute('href'),'tel:0200000000');assert.equal(await latest(p).getByRole('link',{name:'공식 신청 페이지',exact:true}).count(),1);
  await send(p,'전화로 신청할 수 있어?');assert.equal(await latest(p).getByRole('link',{name:'공식 홈페이지',exact:true}).count(),1);
  await tap(p,'다른 활동 보기');assert.equal(await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).count(),0);
 }else{assert.match(await latest(p).innerText(),/이전에 확인한|아직 확인된/)}
 assert.doesNotMatch(await latest(p).innerText(),/무료 요금제|추가 결제|API|검색 사용량/);await layout(p);
 await p.screenshot({path:`/workspace/work/life-browser/chat-${width}-${mode}.png`});console.log('PASS natural mobile chat/region/howto/budget/selection/refusal',width,mode);
 }catch(e){await p.screenshot({path:`/workspace/work/life-browser/failure-${width}-${mode}.png`,fullPage:true});throw e}finally{await p.close()}
}
for(const scenario of ['quota','timeout','empty','page_error']){
 const p=await b.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});await fresh(p,'http://127.0.0.1:18528?case='+scenario);await send(p,'인천 부평구 부평동 수영 찾아줘');const t=await latest(p).innerText();assert.match(t,/지금은 새로운 정보를 찾기 어려워요|아직 확인된 프로그램이 없어요/);assert.doesNotMatch(t,/무료 요금제|추가 결제|검색 사용량|강서구|효도아쿠아|API/);await layout(p);console.log('PASS nontechnical search failure and region isolation',scenario);await p.close();
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
