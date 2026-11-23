// Local Streamlit integration. External links are intercepted, never real submissions.
const {chromium}=require('playwright');const assert=require('assert/strict');
const last=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function change(p,act){await idle(p);const old=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await act();await p.waitForFunction(id=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==id,old);await idle(p);}
async function tap(p,name){name=({'운동':/운동하기/,'취미':/취미 배우기/,'문화':/문화생활/}[name]||name);await change(p,()=>p.getByRole('button',{name,exact:true}).tap());}
async function nav(p,key){await change(p,()=>p.locator('.st-key-'+key+' button').tap());}
async function send(p,text){await p.getByRole('textbox').fill(text);await change(p,()=>p.getByRole('textbox').press('Enter'));}
async function layout(p){await p.waitForFunction(()=>{const es=[...document.querySelectorAll('.stButton button,.stLinkButton a')].filter(e=>e.getClientRects().length);return es.length&&es.every(e=>e.getBoundingClientRect().height>=44)});assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const bad=await p.locator('.stButton button,.stLinkButton a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&(e.getBoundingClientRect().width<44||e.getBoundingClientRect().height<44)).map(e=>e.innerText));assert.deepEqual(bad,[]);}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const [width,mode,port]of [[320,'keyless',18517],[390,'keyless',18517],[768,'keyless',18517],[390,'mock',18518]]){
 const p=await b.newPage({viewport:{width,height:900},isMobile:true,hasTouch:true,colorScheme:width===320||mode==='mock'?'dark':'light'});try{
 await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('button',{name:/운동하기/}).waitFor();await idle(p);
 await tap(p,'운동');await last(p).getByText(/어느 지역|어느 시/).waitFor();await tap(p,'다른 지역 선택');await tap(p,'서울');await tap(p,'강서구');await tap(p,'구 전체에서 찾기');
 const names=await last(p).locator('h3').allTextContents();assert.ok(names.length>0&&names.length<=3);
 await change(p,()=>last(p).getByRole('button',{name:'자세히 보기 →',exact:true}).first().tap());const selected=await last(p).locator('h3').first().innerText();
 await tap(p,'신청 방법 안내 →');await last(p).getByText(/아직 신청·예약·결제가 완료된 것은 아니에요/).waitFor();await last(p).getByText(/신청 방식 ·/).waitFor();await last(p).getByText(/공식 기관 사이트가 새 창/).waitFor();
 const before=await last(p).locator('h3').first().innerText();assert.equal(before,selected);
 for(const [level,px]of [[1,'20px'],[2,'22px']]){await p.getByRole('button',{name:'글자 크기',exact:true}).tap();await p.locator('.st-key-font_choice_'+level+' button').tap();await p.waitForFunction(px=>getComputedStyle(document.querySelector('.stChatInput textarea')).fontSize===px,px);await p.getByRole('dialog').waitFor({state:'hidden'});}
 assert.equal(await last(p).locator('h3').first().innerText(),before);await layout(p);
 await p.screenshot({path:`/workspace/work/button-first/guide-large-${width}-${mode}.png`});
 const link=last(p).getByRole('link',{name:/공식 (신청|안내) 페이지 열기 →/});const href=await link.getAttribute('href');assert.equal(await link.getAttribute('target'),'_blank');
 await p.context().route(url=>url.href===href,route=>route.fulfill({status:200,contentType:'text/html',body:'<title>Offline external link fixture</title>'}));
 const [popup]=await Promise.all([p.waitForEvent('popup'),link.click()]);await popup.waitForLoadState('domcontentloaded');assert.equal(await popup.title(),'Offline external link fixture');await popup.close();
 assert.equal(await last(p).locator('h3').first().innerText(),selected);
 await nav(p,'nav_previous');assert.ok(await last(p).getByRole('button',{name:'신청 방법 안내 →',exact:true}).count());await nav(p,'nav_previous');
 await tap(p,'다른 추천 보기');assert.ok(!((await last(p).locator('h3').allTextContents()).includes(selected)));
 await nav(p,'nav_reselect');await tap(p,'지역 다시 선택');await tap(p,'창원');await tap(p,'성산구');assert.ok((await last(p).innerText()).includes('프로그램 자료는 아직 없어요'));assert.equal(await last(p).locator('h3').count(),0);
 await nav(p,'nav_previous');await last(p).getByText(/어느 구/).waitFor();await nav(p,'nav_reset');await p.getByRole('button',{name:/취미 배우기/}).waitFor();
 await tap(p,'취미');await send(p,'서울 강서구 화곡동');assert.ok((await last(p).innerText()).includes('화곡동'));
 await send(p,'오후가 좋아요');assert.ok(!(await last(p).innerText()).includes('어느 지역에서'));
 await nav(p,'nav_reselect');await tap(p,'시간 다시 선택');await tap(p,'상관없어요');await layout(p);
 await nav(p,'nav_reset');await tap(p,'문화');await tap(p,'서울 강서구에서 찾기');await last(p).getByText(/접수 마감|활동 종료/).first().waitFor();
 if(mode==='mock'){await send(p,'강서구에서 어르신이 참여할 수 있는 운동을 추천해줘');await last(p).getByText(/Gemini 연결을 이용하지 못해 기본 규칙/).waitFor();}
 await layout(p);console.log('PASS buttons-only/region/dong/mixed input/accept/refuse/undo/reset/font/external return/past notices',width,mode);
 }catch(e){await p.screenshot({path:`/workspace/work/button-first/failure-${width}-${mode}.png`,fullPage:true});throw e}finally{await p.close()}
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
