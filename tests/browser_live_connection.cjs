// Local Streamlit + actual SDK with synthetic HTTP transport, never real Gemini/Safari.
const {chromium}=require('playwright'),assert=require('assert/strict');
const last=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning')}
async function click(p,name){await p.getByRole('button',{name,exact:true}).click();await p.waitForTimeout(180);await idle(p)}
async function send(p,text){const old=await p.locator('[id^=latest-reply-]').last().getAttribute('id');const box=p.getByRole('textbox',{name:'질문을 적어주세요'});await box.fill(text);await box.press('Enter');await p.waitForFunction(id=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==id,old);await idle(p)}
async function check(p){assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.equal(await p.getByText('synthetic-sdk-browser-only',{exact:false}).count(),0)}
async function dialog(p){let d=p.getByRole('dialog');await d.waitFor();assert.equal(await p.evaluate(()=>['INPUT','TEXTAREA'].includes(document.activeElement?.tagName)),false);assert.equal(await d.locator('input,textarea,[role=combobox],[contenteditable=true]').count(),0);assert.equal(await p.locator('[class*=st-key-region_option_province_]').count(),17);assert.ok(await p.locator('.st-key-region_touch_list').evaluate(e=>e.scrollHeight>e.clientHeight));return d}
async function choose(p,province,area,dong){await click(p,province+' →');await click(p,area+' →');await click(p,dong+' →');await click(p,'확인');await p.getByRole('dialog').waitFor({state:'detached'});await last(p).getByText(new RegExp('찾는 지역 · '+province+' '+area+' '+dong)).waitFor()}
(async()=>{let b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of [320,390,430,768])for(const mock of [false,true]){
 let p=await b.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true});try{
 await p.goto('http://127.0.0.1:'+(mock?18549:18547));await p.getByRole('button',{name:/취미 배우기/}).waitFor();await idle(p);assert.equal(await p.locator('.st-key-interest_grid_start_interest_ button').count(),4);
 await send(p,'요즘 심심해요');await send(p,'사람들과 어울리고 싶어요');if(mock)assert.match(await last(p).innerText(),/앞서 말씀하신 취미/);else assert.match(await last(p).innerText(),/AI와 연결되지 않아/);
 const count=await p.locator('[data-testid=stChatMessage]').count();await click(p,'＋ 보조 메뉴');await p.getByText('연결 상태 확인',{exact:true}).click();await click(p,'Gemini 실제 상담 연결 테스트');
 if(mock){await p.getByText(/고정 문장 두 번의 상담·응답 검증을 통과/).waitFor();assert.match(await p.locator('[data-testid=stJson]').innerText(),/http_status/)}else{await p.getByText(/실제 상담 테스트를 통과하지 못했어요/).waitFor();assert.match(await p.locator('[data-testid=stJson]').innerText(),/key_missing/)}
 assert.equal(await p.locator('[data-testid=stChatMessage]').count(),count);await check(p);await click(p,'＋ 보조 메뉴');
 await send(p,'수영 배우고 싶어요');await click(p,'지역 선택하기');await dialog(p);await choose(p,'강원특별자치도','강릉시','강남동');
 await click(p,'지역 바꾸기');await dialog(p);await choose(p,'인천광역시','서구','가정1동');
 await click(p,'메뉴');await click(p,'다시 선택');await click(p,'지역 다시 선택');await dialog(p);await click(p,'닫기');await p.getByRole('dialog').waitFor({state:'detached'});
 await click(p,'＋ 보조 메뉴');await p.getByText('AI 도움 없이 찾아보기',{exact:true}).click();await click(p,'찾을 지역 선택');await dialog(p);await choose(p,'서울특별시','강서구','화곡1동');await check(p);
 await p.screenshot({path:`/workspace/work/live-connection-browser/${width}-${mock?'sdk-mock':'keyless'}.png`});console.log('PASS conversation/probe/context/all picker entries',width,mock?'SDK mock':'keyless');
 }catch(e){await p.screenshot({path:`/workspace/work/live-connection-browser/failure-${width}.png`,fullPage:true});throw e}finally{await p.close()}
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
