// Local Streamlit + synthetic HTTP search pages. No actual programme or API key.
const {chromium}=require('playwright');const assert=require('assert/strict');
const latest=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning')}
async function turn(p,action){await idle(p);const id=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await action();await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,id);await idle(p)}
async function send(p,text){await p.getByRole('textbox').fill(text);await turn(p,()=>p.getByRole('textbox').press('Enter'))}
async function tap(p,name){await turn(p,()=>p.getByRole('button',{name,exact:true}).tap())}
async function layout(p){assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const bad=await p.locator('.stButton button,.stLinkButton a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&(e.getBoundingClientRect().width<43||e.getBoundingClientRect().height<43)).map(e=>e.innerText));assert.deepEqual(bad,[])}
async function font(p,level){await idle(p);await p.getByRole('button',{name:'글자 크기',exact:true}).click();await p.getByRole('dialog').waitFor();await p.locator('.st-key-font_choice_'+level+' button').click();await p.waitForFunction(px=>getComputedStyle(document.querySelector('.stChatInput textarea')).fontSize===px,(18+level*2)+'px');await p.getByRole('dialog').waitFor({state:'hidden'});await p.getByRole('button',{name:'글자 크기',exact:true}).click();await p.getByRole('button',{name:new RegExp('✓ '+['보통','크게','아주 크게'][level])}).waitFor();await p.mouse.click(3,100);await p.getByRole('dialog').waitFor({state:'hidden'})}

(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of (process.env.IEUM_FAILURES_ONLY?[]:[320,390,430,768]))for(const mode of ['keyless','mock']){
 const p=await browser.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true,colorScheme:mode==='mock'?'dark':'light'});try{
 await p.goto('http://127.0.0.1:'+(mode==='mock'?18528:18527));await p.getByRole('button',{name:/운동하기/}).waitFor();await idle(p);await p.waitForFunction(()=>getComputedStyle(document.querySelector('.stChatInput textarea')).fontSize==='18px'&&getComputedStyle(document.querySelector('[class*=st-key-interest_grid_] button')).backgroundColor==='rgb(255, 255, 255)');
 const grid=p.locator('.st-key-interest_grid_start_interest_ button');assert.equal(await grid.count(),4);const boxes=await Promise.all((await grid.all()).map(x=>x.boundingBox()));assert.ok(Math.abs(boxes[0].y-boxes[1].y)<3);assert.ok(boxes[1].x>boxes[0].x+boxes[0].width-1);assert.ok(boxes[2].y>boxes[0].y);assert.ok(Math.abs(boxes[2].y-boxes[3].y)<3);
 await font(p,1);await font(p,2);await layout(p);await p.screenshot({path:`/workspace/work/neighbourhood-web/landing-${width}-${mode}.png`});
 await send(p,'화곡동에 살아요. 수영을 배우고 싶어요');await latest(p).getByText(/어느 시·구/).waitFor();await send(p,'서울 강서구요');
 if(mode==='mock'){
  await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();assert.ok((await latest(p).innerText()).includes('공식 출처 확인'));
  await send(p,'다른 시간');await latest(p).getByRole('button',{name:'오후',exact:true}).waitFor();assert.equal(await latest(p).locator('[class*=st-key-web_card_] h3').count(),0);await tap(p,'오후');await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();await send(p,'무료로 찾아줘');await latest(p).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();
  await tap(p,'자세히 보기');await latest(p).getByText(/신청 방법/).first().waitFor();assert.equal(await latest(p).getByRole('link',{name:'전화하기 · 02-0000-0000',exact:true}).getAttribute('href'),'tel:0200000000');assert.ok(await latest(p).getByRole('link',{name:'공식 신청 페이지',exact:true}).count());assert.ok((await latest(p).innerText()).includes('테스트 주소'));assert.ok(await latest(p).getByRole('link',{name:'주소로 길 찾기',exact:true}).count());
  await layout(p);await p.screenshot({path:`/workspace/work/neighbourhood-web/detail-${width}.png`});
  await tap(p,'다른 활동 보기');await latest(p).getByText(/다른 동네까지/).waitFor();assert.equal(await latest(p).locator('[class*=st-key-web_card_] h3').count(),0);await tap(p,'아니요, 이 동네만 볼게요');await send(p,'부천에서 문화센터를 찾아줘');await latest(p).getByText(/아직 확인된 프로그램|찾지 못했/).first().waitFor();assert.equal(await latest(p).locator('[class*=st-key-web_card_] h3').count(),0);
 }else{
  assert.match(await latest(p).innerText(),/아직 확인된|이전에 확인한/);assert.doesNotMatch(await latest(p).innerText(),/무료 요금제|추가 결제|미설정/);
 }
 await layout(p);console.log('PASS mobile grid/font-close/outside/ambiguity/search/details/actions/refusal/fallback',width,mode);
 }catch(e){await p.screenshot({path:`/workspace/work/neighbourhood-web/failure-${width}-${mode}.png`,fullPage:true});throw e}finally{await p.close()}
}
for(const [caseName,message]of [['quota','지금은 새로운|이전에 확인한'],['empty','아직 확인된'],['page_error','아직 확인된'],['timeout','지금은 새로운|이전에 확인한']]){
 const p=await browser.newPage({viewport:{width:390,height:844},hasTouch:true,isMobile:true});await p.goto('http://127.0.0.1:18528?case='+caseName);await p.getByRole('button',{name:/운동하기/}).waitFor();await send(p,'서울 강서구 화곡동 수영');await latest(p).getByText(new RegExp(message)).first().waitFor();await latest(p).getByRole('button',{name:'인터넷 검색 다시 하기',exact:true}).waitFor();await layout(p);await tap(p,'인터넷 검색 다시 하기');await latest(p).getByText(new RegExp(message)).first().waitFor();if(caseName==='page_error'||caseName==='empty'){await tap(p,'저장 자료로 찾아보기');await latest(p).getByText(/아직 확인된|이전에 확인한/).first().waitFor()}else{await latest(p).getByText(/지금은 새로운|이전에 확인한/).first().waitFor()}console.log('PASS safe search failure/retry/cache',caseName);await p.close();
}
const past=await browser.newPage({viewport:{width:390,height:844},hasTouch:true,isMobile:true});await past.goto('http://127.0.0.1:18528?case=past');await past.getByRole('button',{name:/운동하기/}).waitFor();await send(past,'서울 강서구 화곡동 수영');await latest(past).getByRole('heading',{name:'테스트 전용 화곡 수영',exact:true}).waitFor();await tap(past,'자세히 보기');assert.ok((await latest(past).innerText()).includes('운영 종료'));assert.equal(await latest(past).getByRole('link',{name:'공식 신청 페이지',exact:true}).count(),0);console.log('PASS expired programme prevents application action');await past.close();
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
