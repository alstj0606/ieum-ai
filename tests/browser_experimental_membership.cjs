// Touch-input regression on a real local Streamlit server; no official-site actions.
const {chromium}=require('playwright');const assert=require('assert/strict');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function change(p,action){const old=await p.locator('[id^=latest-reply-inst-]').count()?await p.locator('[id^=latest-reply-inst-]').getAttribute('id'):null;await action();await p.waitForFunction(id=>document.querySelector('[id^=latest-reply-inst-]')?.id!==id,old);await idle(p);}
async function tap(p,name){await change(p,()=>p.getByRole('button',{name,exact:true}).tap());}
async function reset(p){await change(p,()=>p.locator('.st-key-inst_reset button').tap());}
async function outcome(p,title,firstAction){await p.getByRole('heading',{name:title,exact:true}).waitFor();await idle(p);assert.ok((await p.locator('.st-key-inst_instruction').innerText()).includes(firstAction));
 await p.waitForFunction(()=>{const h=document.querySelector('[data-testid=stChatMessage] h3')?.getBoundingClientRect();const i=document.querySelector('.st-key-inst_instruction')?.getBoundingClientRect();return h&&i&&h.y>=55&&h.y<170&&i.y>=h.bottom&&i.bottom<innerHeight-90;},null,{timeout:6000});
 assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.ok(await p.locator('.stButton button,[data-testid=stLinkButton] a').evaluateAll(es=>es.filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().height>=48)));
}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const width of [320,390,768])for(const mode of ['normal','visual']){
 const p=await b.newPage({viewport:{width,height:850},hasTouch:true,isMobile:true,colorScheme:mode==='visual'?'dark':'light'});
 try{await p.goto('http://127.0.0.1:18507');await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);
 if(mode==='visual'){await p.getByText('실험 · 버튼 찾기 예시',{exact:true}).tap();await tap(p,'버튼 찾기 예시 시작');}else await tap(p,'온라인 신청 도와주세요');
 await outcome(p,'1단계 / 6단계 · 복지관 회원이신가요?','회원인지');assert.equal(await p.locator('.ieum-signup-visual').count(),0);
 for(const[choice,title]of [['복지관 비회원이에요','비회원 · 방문 회원등록 안내'],['회원 여부를 모르겠어요','회원 여부 확인 안내']]){
  await tap(p,choice);await outcome(p,title,'전화');assert.equal(await p.getByRole('button',{name:choice,exact:true}).count(),0);assert.equal(await p.locator('.ieum-signup-visual').count(),0);
  await tap(p,'다시 설명');await outcome(p,title,'전화');await tap(p,'못 찾겠어요');await outcome(p,title,'전화');
  await p.screenshot({path:`/workspace/work/experiment-selection/${mode}-${width}-${choice.startsWith('복지관')?'nonmember':'unknown'}.png`});await reset(p);
 }
 await tap(p,'복지관 기존 회원이에요');await outcome(p,'2단계 / 6단계 · 기존 회원 · 온라인 아이디 확인','온라인 아이디');
 await tap(p,'온라인 아이디가 있어요 · 로그인 안내');await outcome(p,'3단계 / 6단계 · 온라인 아이디와 로그인을 준비해요','로그인');
 await tap(p,'아이디가 없어요 · 온라인 아이디 만들기');await outcome(p,'1단계 / 5단계 · 공식 사이트를 열어요','공식 사이트 열기');
 const toggle=p.getByRole('switch',{name:'버튼 찾기 예시 보기 · 실제 사이트 아님',exact:true});assert.equal(await toggle.isChecked(),mode==='visual');
 if(mode==='visual'){await p.locator('[data-guide-step=signup_open]').waitFor();await p.locator('.st-key-inst_visual_guide label').tap();await p.locator('.ieum-signup-visual').waitFor({state:'detached'});await idle(p);}
 const input=p.getByRole('textbox');await input.fill('비회원이에요');await change(p,()=>input.press('Enter'));await outcome(p,'비회원 · 방문 회원등록 안내','전화');
 await tap(p,'다시 설명');await reset(p);await tap(p,'복지관 기존 회원이에요');await tap(p,'아이디가 없어요 · 온라인 아이디 만들기');await outcome(p,'1단계 / 5단계 · 공식 사이트를 열어요','공식 사이트 열기');assert.equal(await toggle.isChecked(),false);
 console.log('PASS touch entry/member outcomes/first action/rerun/login/signup/preference cleanup',width,mode);
 }catch(error){await p.screenshot({path:`/workspace/work/experiment-selection/failure-${width}-${mode}.png`,fullPage:true});throw error;}finally{await p.close();}
 }}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
