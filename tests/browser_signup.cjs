// Local Chromium only. Never authenticates or submits information on the official site.
const {chromium}=require('playwright');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function change(p,action){const old=await p.locator('[id^=latest-reply-inst-]').count()?await p.locator('[id^=latest-reply-inst-]').getAttribute('id'):null;await action();await p.waitForFunction(before=>{const e=document.querySelector('[id^=latest-reply-inst-]');return e&&e.id!==before;},old);await idle(p);}
async function click(p,name){await change(p,()=>p.getByRole('button',{name,exact:true}).click());}
async function send(p,text){await p.getByRole('textbox').fill(text);await change(p,()=>p.getByRole('button',{name:'질문 전송',exact:true}).click());}
async function stage(p,n,total=5){await p.getByRole('heading',{name:new RegExp(`^${n}단계 / ${total}단계`)}).waitFor();await idle(p);}
async function layout(p){if(await p.locator('[data-testid=stException]').count())throw Error('Streamlit exception');if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');const failures=await p.locator('.stButton button:not(:disabled),[data-testid=stLinkButton] a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&(e.getBoundingClientRect().height<48||e.getBoundingClientRect().right>innerWidth+1)).map(e=>e.innerText));if(failures.length)throw Error('Touch area/width: '+failures);const text=await p.locator('.st-key-inst_instruction').evaluate(e=>getComputedStyle(e.querySelector('p')).fontSize);if(parseFloat(text)<22)throw Error('Instruction too small');}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const width of (process.env.SIGNUP_WIDTHS?process.env.SIGNUP_WIDTHS.split(',').map(Number):[320,390,768]))for(const[mode,port]of[['keyless',18507],['gemini-mock',18508]]){
const p=await b.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});try{await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);
await click(p,'온라인 신청 도와주세요');await stage(p,1,6);
await click(p,'회원 여부를 모르겠어요');await stage(p,1,6);await p.getByText(/회원 여부를 추측하지/).waitFor();
await click(p,'복지관 비회원이에요');await send(p,'아이디가 없어요');await stage(p,1,6);await p.getByText(/온라인 아이디를 만들기 전에/).waitFor();
await click(p,'복지관 기존 회원이에요');await stage(p,2,6);await click(p,'온라인 아이디가 있어요 · 로그인 안내');await stage(p,3,6);
await click(p,'아이디가 없어요 · 온라인 아이디 만들기');await stage(p,1);await layout(p);
const link=await p.getByRole('link',{name:'공식 신청 사이트 열기 →',exact:true}).getAttribute('href');if(link!=='https://sssenior.e-ncom.co.kr/')throw Error('Official URL changed');
for(let n=2;n<=5;n++){await click(p,'다음 단계 →');await stage(p,n);await layout(p);await click(p,'못 찾겠어요');await stage(p,n);await click(p,'다시 설명');await stage(p,n);}
if(!await p.getByRole('button',{name:'다음 단계 →',exact:true}).isDisabled())throw Error('Unverified next enabled');await p.getByText(/인증 이후/, {exact:false}).first().waitFor();
await send(p,'다음');await stage(p,5);await p.getByText(/인증 이후.*미확인|인증 이후.*미검증/).first().waitFor();
await click(p,'이전 단계');await stage(p,4);await send(p,'위 약관 동의 버튼을 못 찾겠어요 (연결 실패 시험)');await stage(p,4);if(mode==='gemini-mock')await p.getByText('Gemini 연결을 이용하지 못해 기본 안내로 도와드려요.',{exact:true}).waitFor();await layout(p);
await p.screenshot({path:`/workspace/work/signup-${width}-${mode}.png`});
await p.getByText('기존 기능 · 강서구 활동 검색',{exact:true}).click();await p.getByRole('button',{name:'강서구 기존 서비스 열기',exact:true}).click();await p.getByRole('button',{name:'성산복지관 신청 도우미로 돌아가기',exact:true}).waitFor();await idle(p);await p.getByRole('button',{name:'성산복지관 신청 도우미로 돌아가기',exact:true}).click();await stage(p,4);
await click(p,'처음으로');await stage(p,1,6);await send(p,'온라인 아이디 만들기');await stage(p,1);await send(p,'다음');await stage(p,1);await click(p,'복지관 기존 회원이에요');await stage(p,1);await click(p,'다음 단계 →');await stage(p,2);await layout(p);
console.log('PASS signup/membership/navigation/help/unverified boundary/session/layout',width,mode);}catch(error){await p.screenshot({path:`/workspace/work/signup-failure-${width}-${mode}.png`,fullPage:true});throw error;}finally{await p.close();}
}}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
