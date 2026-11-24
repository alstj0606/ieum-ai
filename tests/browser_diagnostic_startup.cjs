// Real local Streamlit; failure mode injects TypeError, never a live API claim.
const {chromium}=require('playwright'),assert=require('assert/strict');
const last=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning')}
async function click(p,name){await p.getByRole('button',{name,exact:true}).click();await p.waitForTimeout(150);await idle(p)}
async function send(p,text){const id=await p.locator('[id^=latest-reply-]').last().getAttribute('id');const box=p.getByRole('textbox',{name:'질문을 적어주세요'});await box.fill(text);await box.press('Enter');await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,id);await idle(p)}
async function check(p){assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.equal(await p.getByText('synthetic-private-value-not-for-logs',{exact:false}).count(),0)}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of [320,390,768])for(const failure of [false,true]){
 const p=await b.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true});try{
 await p.goto('http://127.0.0.1:'+(failure?18539:18537));await p.getByRole('button',{name:/취미 배우기/}).waitFor();await idle(p);
 assert.equal(await p.locator('.st-key-interest_grid_start_interest_ button').count(),4);assert.equal(await p.locator('[data-testid=stJson]').count(),0);await check(p);
 await click(p,'＋ 보조 메뉴');await p.getByText('연결 상태 확인',{exact:true}).click();await p.getByRole('button',{name:'연결 진단 실행',exact:true}).waitFor();assert.equal(await p.locator('[data-testid=stJson]').count(),0);
 await click(p,'＋ 보조 메뉴');await send(p,'수영 배우고 싶어요');await last(p).getByText(/어느 동네/).waitFor();const history=await p.locator('[data-testid=stChatMessage]').count();
 await click(p,'＋ 보조 메뉴');if(!await p.getByRole('button',{name:'연결 진단 실행',exact:true}).isVisible())await p.getByText('연결 상태 확인',{exact:true}).click();await click(p,'연결 진단 실행');
 if(failure){await p.getByText(/연결 상태는 확인되지 않았어요/).waitFor();assert.equal(await p.locator('[data-testid=stJson]').count(),0)}else{await p.locator('[data-testid=stJson]').waitFor()}
 await check(p);assert.equal(await p.locator('[data-testid=stChatMessage]').count(),history);await click(p,'＋ 보조 메뉴');
 await click(p,'지역 선택하기');const dialog=p.getByRole('dialog');await dialog.waitFor();assert.equal(await dialog.locator('input,textarea,[role=combobox]').count(),0);
 await click(p,'강원특별자치도 →');await click(p,'강릉시 →');await click(p,'강남동 →');await click(p,'확인');await dialog.waitFor({state:'detached'});await last(p).getByText(/찾는 지역 · 강원특별자치도 강릉시 강남동/).waitFor();
 await send(p,'요즘 심심해요');await check(p);assert.doesNotMatch(await last(p).innerText(),/어느 동네에서 찾아볼까요/);
 await p.screenshot({path:`/workspace/work/diagnostic-browser/${width}-${failure?'failure':'normal'}.png`});console.log('PASS real startup/menu/on-demand diagnostic/chat/location',width,failure?'injected failure':'keyless');
 }catch(e){await p.screenshot({path:`/workspace/work/diagnostic-browser/failure-${width}.png`});throw e}finally{await p.close()}
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
