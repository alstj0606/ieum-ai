// Default user-centred app. Mock mode uses localhost Gemini/STT/TTS, never real keys.
const {chromium}=require('playwright');const assert=require('assert/strict');const fs=require('fs');
const rows=JSON.parse(fs.readFileSync('data/activities.json','utf8'));
const latest=p=>p.locator('[data-testid=stChatMessage]').last();
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function change(p,action){const before=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await action();await p.waitForFunction(old=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==old,before);await idle(p);}
async function tap(p,name){await change(p,()=>p.getByRole('button',{name,exact:true}).tap());}
async function send(p,text){await idle(p);const input=p.getByRole('textbox');await input.fill(text);await change(p,()=>input.press('Enter'));}
async function layout(p){assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const failures=await p.locator('.stButton button,[data-testid=stLinkButton] a').evaluateAll(es=>es.filter(e=>e.getClientRects().length&&e.getBoundingClientRect().height<48).map(e=>e.innerText));assert.deepEqual(failures,[]);}
async function newAnswerVisible(p){await p.waitForFunction(()=>{const a=[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.getBoundingClientRect();return a&&a.y>=55&&a.y<170;},null,{timeout:6000});}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});try{for(const width of [320,390,768])for(const[mode,port]of[['keyless',18517],['mock',18518]]){
 const p=await b.newPage({viewport:{width,height:900},isMobile:true,hasTouch:true,colorScheme:mode==='mock'?'dark':'light'});
 try{await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('heading',{name:'오늘은 무엇을 해보고 싶으세요?',exact:true}).waitFor();await idle(p);await p.waitForFunction(()=>getComputedStyle(document.querySelector('[data-testid=stApp]')).backgroundColor==='rgb(255, 255, 255)');await newAnswerVisible(p);await layout(p);
 assert.equal(await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).count(),0);if(mode==='keyless')assert.ok(await p.getByRole('button',{name:'음성 입력 · 현재 설정되지 않았어요',exact:true}).isDisabled());
 await p.screenshot({path:`/workspace/work/discovery/landing-${width}-${mode}.png`});
 await tap(p,'수영을 배우고 싶어요');await latest(p).getByText(/어느 지역/).waitFor();await tap(p,'서울 강서구에서 찾기');await latest(p).getByRole('heading',{name:'공항동문화체육센터 효도아쿠아',exact:true}).waitFor();assert.ok((await latest(p).innerText()).includes('유사 활동'));
 assert.ok(await latest(p).getByRole('button',{name:'자세히 보기 →',exact:true}).count()<=3);
 await change(p,()=>latest(p).getByRole('button',{name:'자세히 보기 →',exact:true}).first().tap());await newAnswerVisible(p);await latest(p).getByText('상세 정보 · 신청 방법·공식 근거',{exact:true}).waitFor();
 const source=rows.find(r=>r.activity_type==='아쿠아로빅');assert.equal(await latest(p).getByRole('link',{name:'공식 사이트 이동 →',exact:true}).getAttribute('href'),source.official_url||source.source_url);
 await change(p,()=>latest(p).getByRole('button',{name:'신청 방법 안내 →',exact:true}).tap());await latest(p).getByText(/아직 신청·예약·결제가 완료된 것은 아니에요/).waitFor();await newAnswerVisible(p);
 await send(p,'창원 성산구요');assert.ok((await latest(p).innerText()).includes('지역의 프로그램 자료는 아직 없어요'));assert.equal(await latest(p).getByRole('button',{name:'자세히 보기 →',exact:true}).count(),0);
 await send(p,'서울 강서구 슬로우 러닝 프로그램');await latest(p).getByRole('heading',{name:'2026년 하반기 생활체육교실 슬로우조깅 (40세 이상)',exact:true}).waitFor();assert.ok((await latest(p).innerText()).includes('접수 마감'));
 const titles=await latest(p).locator('h3').allTextContents();assert.ok(titles[0].includes('슬로우조깅'));assert.ok(titles.length<=3);
 await send(p,'오후로 찾아줘');assert.ok(!(await latest(p).locator('h3').allTextContents()).some(x=>x.includes('슬로우조깅')));await send(p,'무료로 찾아줘');assert.ok((await latest(p).innerText()).includes('무료'));
 if(mode==='mock'){await send(p,'강서구에서 어르신이 참여할 수 있는 운동을 추천해줘');await latest(p).getByText(/Gemini 연결을 이용하지 못해 기본 규칙/).waitFor();assert.ok(!(await latest(p).innerText()).includes('private-'));}
 await p.getByRole('button',{name:'＋ 보조 메뉴',exact:true}).tap();await tap(p,'처음부터 다시 찾기');await p.getByRole('button',{name:'수영을 배우고 싶어요',exact:true}).waitFor();await newAnswerVisible(p);
 await tap(p,'사람들과 함께하는 활동이 좋아요');await tap(p,'서울 강서구에서 찾기');await layout(p);assert.ok((await latest(p).innerText()).includes('교류')||(await latest(p).innerText()).includes('함께'));
 await p.screenshot({path:`/workspace/work/discovery/results-${width}-${mode}.png`});
 if(mode==='mock'&&width===390){
  await p.getByRole('button',{name:'＋ 보조 메뉴',exact:true}).tap();await tap(p,'처음부터 다시 찾기');await idle(p);const cdp=await p.context().newCDPSession(p);
  await cdp.send('Browser.setPermission',{permission:{name:'microphone'},setting:'granted',origin:`http://127.0.0.1:${port}`});
  await p.locator('[data-testid=stChatInputMicButton]').tap();await p.locator('[data-testid=stChatInputApproveButton]').waitFor();await p.waitForTimeout(900);
  await change(p,()=>p.locator('[data-testid=stChatInputApproveButton]').tap());await latest(p).getByRole('heading',{name:rows.find(r=>r.activity_type==='국악공연').name,exact:true}).waitFor();await p.locator('audio').first().waitFor();
  await p.getByText('음성인식이 다르게 되었나요?',{exact:true}).tap();await p.getByRole('button',{name:'글자 수정하기',exact:true}).tap();await p.getByRole('textbox',{name:'인식된 문장 수정',exact:true}).fill('강서구 가드닝');await tap(p,'고친 질문 보내기');
  console.log('PASS mocked voice capture/STT/TTS/correction chain');
  // A fresh browser without auto-grant avoids the successful recording's cached stream.
  const deniedBrowser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-fake-device-for-media-stream']});
  try{const denied=await deniedBrowser.newPage({viewport:{width,height:900},hasTouch:true,isMobile:true});
   await denied.addInitScript(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{try{return await original(...args)}catch(e){window.ieumTestMediaFailure=e.name;throw e}}});
   const control=await denied.context().newCDPSession(denied);await control.send('Browser.setPermission',{permission:{name:'microphone'},setting:'denied',origin:`http://127.0.0.1:${port}`});
   await denied.goto(`http://127.0.0.1:${port}`);await denied.locator('[data-testid=stChatInputMicButton]').waitFor();await idle(denied);await denied.locator('[data-testid=stChatInputMicButton]').tap();
   await denied.waitForFunction(()=>window.ieumTestMediaFailure==='NotAllowedError');await denied.getByRole('textbox').waitFor();await send(denied,'강서구 국악');await latest(denied).getByRole('heading',{name:rows.find(r=>r.activity_type==='국악공연').name,exact:true}).waitFor();console.log('PASS simulated microphone permission denial/text fallback');await denied.close();
  }finally{await deniedBrowser.close();}
 }
 console.log('PASS discovery examples/conditions/factual alternatives/details/application/region/reset/mobile',width,mode);
 }catch(error){await p.screenshot({path:`/workspace/work/discovery/failure-${width}-${mode}.png`,fullPage:true});throw error;}finally{await p.close();}
 }}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
