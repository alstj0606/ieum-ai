// Local Streamlit only: mobile Chromium viewports, mock Gemini HTTP, no external application.
const {chromium}=require('playwright');
const last=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function changed(p,before){await p.waitForFunction(old=>{const a=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1);return a&&a.id!==old;},before);await idle(p);}
async function anchor(p){return p.evaluate(()=>[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1)?.id||null);}
async function send(p,text){const old=await anchor(p);await p.getByRole('textbox').fill(text);await p.getByRole('button',{name:'질문 전송',exact:true}).click();await changed(p,old);}
async function click(p,name){const old=await anchor(p);await last(p).getByRole('button',{name,exact:true}).click();await changed(p,old);}
async function startVisible(p){await p.waitForFunction(()=>{const e=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1)?.getBoundingClientRect();return e&&e.y>=0&&e.y<160;},null,{timeout:6000});}
async function stage(p,n,total=5){await last(p).getByRole('heading',{name:`${n}단계 / ${total}단계`,exact:true}).waitFor();await startVisible(p);if(await p.locator('[data-testid=stException]').count())throw Error('Streamlit exception');}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const width of [320,390,768])for(const[mode,port]of[['basic',18502],['gemini-mock',18504]]){
 const p=await b.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
 await send(p,'65세이고 강서구에서 가볍게 운동하고 싶어요.');await last(p).getByRole('heading',{name:/서남센터/}).waitFor();
 await send(p,'오후가 좋아요.');await last(p).getByText(/앞서 안내한 활동과 순서는 같아요/).waitFor();
 let text=await last(p).innerText();if(!text.includes('유지한 조건')||!text.includes('강서구')||!text.includes('65세')||!text.includes('공식 자료에 오후 회차'))throw Error('Missing factual delta');
 if(await last(p).getByRole('heading',{name:/서남센터/}).count())throw Error('Full card repeated');
 if(await p.getByRole('heading',{name:/서남센터/}).count()!==1)throw Error('Original card lost/duplicated');
 await click(p,'신청 도와주세요 →');await stage(p,1);const link=last(p).getByRole('link',{name:'공식 신청 페이지 열기 →',exact:true});if(!(await link.getAttribute('href')).includes('S230131090246367142'))throw Error('Wrong official URL');
 await click(p,'추천으로 돌아가기');await send(p,'신청 도와주세요');await stage(p,1);
 await click(p,'이 단계를 확인했어요 · 다음 단계 →');await stage(p,2);await last(p).getByText('공식 사이트의 메뉴·버튼 → 로그인',{exact:true}).waitFor();
 await click(p,'이전 단계');await stage(p,1);await click(p,'다시 설명');await stage(p,1);
 await click(p,'이 단계를 확인했어요 · 다음 단계 →');await stage(p,2);
 // Same preference keeps selected programme/guide progress while only explaining the update.
 await send(p,'오후가 좋아요. (연결 실패 시험)');
 await last(p).getByText(/앞서 안내한 활동과 순서는 같아요/).waitFor();if(mode==='gemini-mock')await last(p).getByText('Gemini 연결을 이용하지 못해 기본 규칙으로 안내하고 있어요.',{exact:true}).waitFor();
 await send(p,'오전이 좋아요');await last(p).getByText(/앞서 안내한 활동과 순서는 같아요/).waitFor();
 await click(p,'신청 안내 이어보기 →');await stage(p,2);await send(p,'신청 방법 알려줘');await stage(p,2);
 for(let n=3;n<=5;n++){await click(p,'이 단계를 확인했어요 · 다음 단계 →');await stage(p,n);}
 await click(p,'안내를 끝까지 확인했어요');await last(p).getByText('안내를 끝까지 확인했어요. 실제 신청 결과는 공식 사이트에서 직접 확인해 주세요.',{exact:true}).waitFor();
 await send(p,'무료로 찾아줘');await last(p).getByText(/무료 예산을 필수로/).waitFor();text=await last(p).innerText();if(!text.includes('바뀐 조건에 맞는 결과에서 빠졌어요'))throw Error('No result change explanation');
 if(await last(p).getByRole('heading',{name:/서남센터/}).count())throw Error('Paid programme retained as free');
 await send(p,'강서구 걷기 프로그램 찾아줘');await last(p).getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).waitFor();
 await click(p,'슬로우조깅 정보 보기 →');await click(p,'접수 상태·다음 모집 확인 도우미 →');await stage(p,1,2);await last(p).getByText(/접수 마감 · 다음 접수 일정 미정/).waitFor();
 if(await last(p).getByRole('link',{name:'공식 신청 페이지 열기 →',exact:true}).count())throw Error('Closed guide offers booking');
 await click(p,'이 단계를 확인했어요 · 다음 단계 →');await stage(p,2,2);await last(p).getByText('공식 사이트의 메뉴·버튼 → 목록보기',{exact:true}).waitFor();
 await send(p,'강서구 정비사업 시민교육 배우고 싶어요');await last(p).getByRole('heading',{name:/정비사업/}).waitFor();await click(p,'신청 도와주세요 →');await stage(p,1,1);
 await last(p).getByText('다른 신청 방법·문의·공식 근거',{exact:true}).click();await last(p).getByRole('link',{name:'📞 02-464-4114 문의 전화하기',exact:true}).waitFor();
 if(await last(p).getByRole('link',{name:/신청 전화하기/}).count())throw Error('Inquiry sold as application');
 text=await last(p).innerText();for(const term of ['방문 신청 · 공식 자료에 안내됨','방문 접수 장소 · 공식 자료 확인 필요','방문 접수 가능 시간 · 공식 자료 확인 필요'])if(!text.includes(term))throw Error('Missing visit facts '+term);
 if(/\d{4}-\d{2}-\d{2}T/.test(text))throw Error('Raw ISO date');if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow');
 await p.screenshot({path:`/workspace/work/helper-${width}-${mode}.png`});console.log('PASS continuity/delta/compact chat -> online stages/back/repeat/resume -> free -> closed guide -> programme reset -> inquiry/visit',width,mode);await p.close();
 }}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
