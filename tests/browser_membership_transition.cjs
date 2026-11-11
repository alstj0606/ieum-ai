// Real local Streamlit reruns, no official-site interaction or real provider calls.
const {chromium}=require('playwright');const assert=require('assert/strict');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function turn(p,action){const old=await p.locator('[id^=latest-reply-inst-]').count()?await p.locator('[id^=latest-reply-inst-]').getAttribute('id'):null;await action();await p.waitForFunction(id=>document.querySelector('[id^=latest-reply-inst-]')?.id!==id,old);await idle(p);}
async function click(p,name){await turn(p,()=>p.getByRole('button',{name,exact:true}).click());}
async function send(p,text){await idle(p);const input=p.getByRole('textbox');await input.fill(text);await turn(p,()=>input.press('Enter'));}
async function visibleOutcome(p,title,action){await p.getByRole('heading',{name:title,exact:true}).waitFor();await p.waitForFunction(()=>{const heading=document.querySelector('[data-testid=stChatMessage] h3')?.getBoundingClientRect();const instruction=document.querySelector('.st-key-inst_instruction')?.getBoundingClientRect();return heading&&instruction&&heading.y>=55&&heading.y<170&&instruction.y>=heading.bottom&&instruction.bottom<innerHeight-90;},null,{timeout:6000});
 assert.ok((await p.locator('.st-key-inst_instruction').innerText()).includes(action));assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 const sizes=await p.locator('.stButton button,[data-testid=stLinkButton] a').evaluateAll(es=>es.filter(e=>e.getClientRects().length).map(e=>e.getBoundingClientRect().height));assert.ok(sizes.every(h=>h>=48));
}
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const scheme of ['light','dark'])for(const width of [320,390,768]){
 const p=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true,colorScheme:scheme});
 try{
 await p.goto('http://127.0.0.1:18507');await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);await click(p,'온라인 신청 도와주세요');
 await click(p,'복지관 비회원이에요');await visibleOutcome(p,'비회원 · 방문 회원등록 안내','전화');
 assert.equal(await p.getByRole('button',{name:'복지관 비회원이에요',exact:true}).count(),0);assert.equal(await p.getByRole('button',{name:'다음 단계 →',exact:true}).count(),0);
 assert.equal(await p.getByRole('link',{name:'기관에 문의 전화하기 · 055-714-9178',exact:true}).getAttribute('href'),'tel:0557149178');
 await p.screenshot({path:`/workspace/work/membership-fix/after-${scheme}-${width}.png`});
 await click(p,'다시 설명');await visibleOutcome(p,'비회원 · 방문 회원등록 안내','전화');await click(p,'못 찾겠어요');await visibleOutcome(p,'비회원 · 방문 회원등록 안내','전화');
 await send(p,'다음');await visibleOutcome(p,'비회원 · 방문 회원등록 안내','전화');
 await click(p,'회원 유형 다시 선택');await click(p,'회원 여부를 모르겠어요');await visibleOutcome(p,'회원 여부 확인 안내','문의 전화');
 assert.equal(await p.getByRole('button',{name:'회원 여부를 모르겠어요',exact:true}).count(),0);await click(p,'다시 설명');await visibleOutcome(p,'회원 여부 확인 안내','문의 전화');
 await click(p,'회원 유형 다시 선택');await click(p,'복지관 기존 회원이에요');await visibleOutcome(p,'2단계 / 6단계 · 기존 회원 · 온라인 아이디 확인','온라인 아이디');
 await click(p,'온라인 아이디가 있어요 · 로그인 안내');await visibleOutcome(p,'3단계 / 6단계 · 온라인 아이디와 로그인을 준비해요','로그인');
 await click(p,'아이디가 없어요 · 온라인 아이디 만들기');await visibleOutcome(p,'1단계 / 5단계 · 공식 사이트를 열어요','공식 사이트 열기');
 await p.locator('.st-key-inst_visual_guide label').click();await p.locator('[data-guide-step=signup_open]').waitFor();await idle(p);
 await click(p,'다음 단계 →');await p.locator('[data-guide-step=signup_menu]').waitFor();
 await send(p,'비회원이에요');await visibleOutcome(p,'비회원 · 방문 회원등록 안내','전화');assert.equal(await p.locator('.ieum-signup-visual').count(),0);
 await click(p,'회원 유형 다시 선택');await click(p,'복지관 기존 회원이에요');await click(p,'아이디가 없어요 · 온라인 아이디 만들기');await visibleOutcome(p,'1단계 / 5단계 · 공식 사이트를 열어요','공식 사이트 열기');
 console.log('PASS membership outcomes/first action/scroll/rerun/type changes/visual isolation/layout',width,scheme);
 }catch(error){await p.screenshot({path:`/workspace/work/membership-fix/failure-${scheme}-${width}.png`,fullPage:true});throw error;}finally{await p.close();}
 }}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
