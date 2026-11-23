// Real local Streamlit UI; optional local SDK mock, never real API credentials.
const {chromium}=require('playwright');const assert=require('assert/strict');const fs=require('fs');
const latest=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function change(p,action){const old=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await action();await p.waitForFunction(id=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==id,old);await idle(p);}
async function send(p,text){await idle(p);await p.getByRole('textbox').fill(text);await change(p,()=>p.getByRole('textbox').press('Enter'));}
async function tap(p,name){const target=p.getByRole('button',{name,exact:true});if((!(await target.count())||!(await target.isVisible()))&&await p.getByText('예시 문장으로 시작',{exact:true}).count())await p.getByText('예시 문장으로 시작',{exact:true}).click();await change(p,()=>latest(p).getByRole('button',{name,exact:true}).tap());}
async function layout(p){await p.waitForFunction(()=>{const es=[...document.querySelectorAll('.stButton button,.stLinkButton a')].filter(e=>e.getClientRects().length);return es.length>0&&es.every(e=>parseFloat(getComputedStyle(e).minHeight)>=44&&e.getBoundingClientRect().height>=44)});assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const bad=await p.locator('.stButton button,.stLinkButton a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&e.getBoundingClientRect().height<44).map(e=>e.innerText));assert.deepEqual(bad,[]);}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of [320,390,768])for(const [mode,port]of [['keyless',18517],['mock',18518]]){
 const p=await b.newPage({viewport:{width,height:900},hasTouch:true,isMobile:true,colorScheme:mode==='mock'?'dark':'light'});
 try{
 await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('heading',{name:'오늘은 어떤 활동을 해보고 싶으세요?',exact:true}).waitFor();await p.getByRole('button',{name:/운동하기/}).waitFor();await idle(p);await layout(p);
 await p.screenshot({path:`/workspace/work/conversational/home-${width}-${mode}.png`});
 await tap(p,'수영을 배우고 싶어요');await latest(p).getByText(/어느 지역|어느 시/).waitFor();
 await tap(p,'서울 강서구에서 찾기');await latest(p).getByRole('heading',{name:'공항동문화체육센터 효도아쿠아',exact:true}).waitFor();assert.ok((await latest(p).innerText()).includes('유사 활동'));
 assert.equal(await latest(p).getByRole('button',{name:'네, 인접 지역도 확인',exact:true}).count(),0);
 const messages=p.locator('[data-testid=stChatMessage]');const user=messages.filter({has:p.locator('[data-ieum-role=user]')}).last();const ub=await user.boundingBox(),ab=await latest(p).boundingBox();assert.ok(ub.x>ab.x);assert.equal(await user.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 240, 226)');
 await send(p,'좋아요');await latest(p).getByText('문의 전화 · 확인 필요',{exact:true}).waitFor();assert.equal(await latest(p).locator('h3').count(),1);assert.ok((await latest(p).innerText()).includes('주소'));
 const source=JSON.parse(fs.readFileSync('data/activities.json','utf8')).find(r=>r.activity_type==='아쿠아로빅');assert.equal(await latest(p).getByRole('link',{name:'공식 사이트 이동 →',exact:true}).getAttribute('href'),source.official_url);
 await layout(p);await p.screenshot({path:`/workspace/work/conversational/details-${width}-${mode}.png`});
 await tap(p,'추천으로 돌아가기');await latest(p).getByRole('button',{name:'자세히 보기 →',exact:true}).waitFor();
 await tap(p,'다른 추천 보기');assert.equal(await latest(p).locator('h3').count(),0);assert.ok((await latest(p).innerText()).includes('자료'));assert.ok((await latest(p).innerText()).includes('부족'));
 await tap(p,'인접 지역도 찾아보기');await latest(p).getByRole('button',{name:'네, 인접 지역도 확인',exact:true}).waitFor();await tap(p,'아니요, 이 지역만 볼게요');assert.ok(!(await latest(p).innerText()).includes('공항동문화체육센터 효도아쿠아'));
 await send(p,'인접 지역도 찾아줘');await tap(p,'네, 인접 지역도 확인');assert.ok((await latest(p).innerText()).includes('현재 확인된 인접 지역 프로그램 자료가 없습니다'));assert.equal(await latest(p).locator('h3').count(),0);
 await send(p,'대화 초기화');await p.getByRole('heading',{name:'오늘은 어떤 활동을 해보고 싶으세요?',exact:true}).waitFor();assert.equal(await p.locator('[data-testid=stChatMessageAvatarUser]').count(),0);
 await tap(p,'문화 행사를 보고 싶어요');await tap(p,'서울 강서구에서 찾기');await send(p,'무료로 찾아줘');await latest(p).locator('h3').nth(1).waitFor();const names=await latest(p).locator('h3').allTextContents();assert.ok(names.length>1&&names.length<=3);
 await send(p,'좋아요');await latest(p).getByText(/어떤 활동이 마음에/).waitFor();await send(p,'2번');assert.equal(await latest(p).locator('h3').first().innerText(),names[1]);
 await tap(p,'신청 방법 안내 →');await latest(p).getByText(/아직 신청·예약·결제가 완료된 것은 아니에요/).waitFor();
 await send(p,'오후로 찾아줘');assert.ok(!(await latest(p).innerText()).includes('어느 지역에서'));await layout(p);
 console.log('PASS interest/region/accept/details/back/refusal/consent/selection/application/reset/bubbles',width,mode);
 }catch(e){await p.screenshot({path:`/workspace/work/conversational/failure-${width}-${mode}.png`,fullPage:true});throw e}finally{await p.close()}
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
