// Local-only institution UI and mocked Gemini. No official login or application submitted.
const {chromium}=require('playwright');const last=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function stage(p,n){await p.getByRole('heading',{name:new RegExp(`^${n}단계 / 6단계`)}).waitFor();await idle(p);}
async function send(p,text){const id=await p.locator('[id^=latest-reply-inst-]').getAttribute('id');await p.getByRole('textbox').fill(text);await p.getByRole('button',{name:'질문 전송',exact:true}).click();await p.waitForFunction(old=>document.querySelector('[id^=latest-reply-inst-]')?.id!==old,id);await idle(p);}
async function click(p,name){const old=await p.locator('[id^=latest-reply-inst-]').count()?await p.locator('[id^=latest-reply-inst-]').getAttribute('id'):null;await p.getByRole('button',{name,exact:true}).click();if(!name.includes('강서구 기존')&&!name.includes('돌아가기'))await p.waitForFunction(before=>{const e=document.querySelector('[id^=latest-reply-inst-]');return e&&e.id!==before;},old);await idle(p);}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const width of [320,390,768])for(const[mode,port]of[['basic',18507],['gemini-mock',18508]]){
 const p=await b.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);await p.waitForFunction(()=>[...document.querySelectorAll('.stButton button')].filter(b=>['프로그램 알아보기','온라인 신청 도와주세요','복지관 회원가입 안내'].includes(b.innerText.trim())).length===3&&[...document.querySelectorAll('.stButton button')].every(b=>b.getBoundingClientRect().height>=48));
 for(const name of ['프로그램 알아보기','온라인 신청 도와주세요','복지관 회원가입 안내']){const box=await p.getByRole('button',{name,exact:true}).boundingBox();if(box.height<48)throw Error('Small action');}
 if((await p.locator('body').innerText()).includes('서남센터'))throw Error('Institutions mixed at start');
 await click(p,'온라인 신청 도와주세요');await stage(p,1);await send(p,'다음');await stage(p,1);
 await click(p,'복지관 비회원이에요');await p.getByText('성산노인종합복지관 · 경남 창원시 성산구 창이대로 781',{exact:true}).waitFor();await send(p,'다음');await stage(p,1);
 await click(p,'복지관 기존 회원이에요');await stage(p,2);const official=await p.getByRole('link',{name:'공식 신청 사이트 열기 →',exact:true}).getAttribute('href');if(official!=='https://sssenior.e-ncom.co.kr/main/index.do')throw Error('Wrong institution link');
 await send(p,'다음');await stage(p,3);await send(p,'로그인이 어려워요');await stage(p,3);await p.getByText(/본인인증은 본인임을 확인하는 별도 과정/).waitFor();
 await send(p,'로그인했는데 다음에 뭘 해야 해요');await stage(p,4);await send(p,'수강신청 버튼을 못 찾겠어요');await stage(p,4);await p.getByText(/4단계에서 막히셨군요/).waitFor();
 await send(p,'버튼을 못 찾겠어요 (연결 실패 시험)');await stage(p,4);if(mode==='gemini-mock')await p.getByText('Gemini 연결을 이용하지 못해 기본 안내로 도와드려요.',{exact:true}).waitFor();
 await send(p,'이전');await stage(p,3);await click(p,'다시 설명');await stage(p,3);await click(p,'다음 단계 →');await stage(p,4);
 await p.waitForFunction(()=>{const r=document.querySelector('[id^=latest-reply-inst-]')?.getBoundingClientRect();return r&&r.y>=0&&r.y<160;},null,{timeout:6000});
 await send(p,'다음');await stage(p,5);await send(p,'다음');await stage(p,6);await send(p,'신청 완료됐나요');await stage(p,6);await p.getByText(/실제 신청 완료를 확인할 수 없어요/).waitFor();
 if(!(await p.locator('body').innerText()).includes('이미지가 없어 글로 안내'))throw Error('No image fallback');if(await p.locator('[data-testid=stException]').count())throw Error('Streamlit exception');if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow');
 await p.screenshot({path:`/workspace/work/seongsan-${width}-${mode}.png`});
 await p.getByText('기존 기능 · 강서구 활동 검색',{exact:true}).click();await click(p,'강서구 기존 서비스 열기');await p.getByRole('button',{name:'성산복지관 신청 도우미로 돌아가기',exact:true}).waitFor();
 await p.getByRole('textbox').fill('강서구 걷기 프로그램 찾아줘');await p.getByRole('button',{name:'질문 전송',exact:true}).click();await p.getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).waitFor();
 await click(p,'성산복지관 신청 도우미로 돌아가기');await stage(p,6);await click(p,'처음부터 다시');await stage(p,1);
 console.log('PASS institution gate/next/stuck/login/back/reset/failure/image fallback/status/legacy roundtrip',width,mode);await p.close();
 }}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
