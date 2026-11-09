// Chromium + local mock API only. No real OpenAI/Safari/physical phone assertion.
const {chromium}=require('playwright');
const URL='http://127.0.0.1:18504';
async function ready(page,url=URL){await page.goto(url);await page.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();}
async function idle(page){await page.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function send(page,text){await page.getByRole('textbox').fill(text);await page.getByRole('button',{name:'질문 전송',exact:true}).click();await page.getByText(text,{exact:true}).last().waitFor();await idle(page);}
async function concert(page){await page.getByRole('heading',{name:'2026 제27회 강서국악한마당',exact:true}).last().waitFor();await idle(page);}
async function details(page){await page.getByText('자세히 보기',{exact:true}).last().click();}
async function main(){
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try{
  for(const width of [320,390,768]){
   const page=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});
   await ready(page,'http://127.0.0.1:18502');
   if(await page.locator('[data-testid="stFileUploader"]').isVisible())throw Error('Upload exposed');
   const mic=page.getByRole('button',{name:'마이크로 말하기',exact:true});const box=await mic.boundingBox();
   if(box.width<64||box.height<64)throw Error('Mic too small');
   await page.getByRole('textbox').fill('수영');
   if(await mic.isVisible())throw Error('Mic active while typing');
   const submit=page.getByRole('button',{name:'질문 전송',exact:true});await submit.waitFor();
   const sent=await submit.boundingBox();
   const root=await page.locator('[data-testid="stChatInput"]').boundingBox();
   const secondary=await page.getByRole('button',{name:'음성 입력으로 돌아가기',exact:true}).boundingBox();
   if(Math.abs(sent.x-box.x)>2||Math.abs(sent.y-box.y)>2)throw Error('Primary action moved');
   for(const r of [sent,secondary])if(r.x<root.x||r.y<root.y||r.x+r.width>root.x+root.width||r.y+r.height>root.y+root.height)throw Error('Button outside rounded input');
   if(await page.locator('#ieum-voice-back').count())throw Error('Extra microphone injected');
   await page.getByRole('button',{name:'음성 입력으로 돌아가기',exact:true}).click();
   await mic.waitFor();
   if(await page.getByRole('textbox').inputValue())throw Error('Voice return did not clear draft');
   await send(page,'국악 공연');
   await page.getByRole('button',{name:'서울 강서구에서 찾기',exact:true}).click();
   await concert(page);
   const last=page.locator('[data-testid="stChatMessage"]').last();
   if(await last.getByRole('heading',{name:'2026 제27회 강서국악한마당',exact:true}).count()!==1)throw Error('Card outside answer');
   await details(page);
   await page.getByRole('button',{name:'이 활동 신청 방법',exact:true}).click();
   await page.getByText('아직 신청·예약·결제가 완료된 것은 아니에요.',{exact:false}).last().waitFor();
   // Wait for the server render and its deferred latest-answer scroll before viewport testing.
   await page.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');
   await page.waitForTimeout(700);
   await page.getByRole('textbox').focus();
   await page.setViewportSize({width,height:480});
   await page.waitForTimeout(800);
   const input=await page.locator('[data-testid="stChatInput"]').boundingBox();
   if(input.y<0||input.y+input.height>481)throw Error('Composer outside reduced viewport');
   const latest=await page.locator('[id^=latest-reply-]').last().boundingBox();
   if(latest.y<0||latest.y>input.y)throw Error('Latest answer hidden behind composer '+JSON.stringify({width,latest,input}));
   const layout=await page.evaluate(()=>({w:innerWidth,scroll:document.documentElement.scrollWidth,
    overflow:[...document.querySelectorAll('.stMain p,.stMain button,.stChatInput')].some(e=>{let r=e.getBoundingClientRect();return r.width>0&&(r.right>innerWidth+1||r.left<0)})}));
   if(layout.scroll>width||layout.overflow)throw Error(JSON.stringify(layout));
   console.log('PASS chat/followup/cards/application/Korean names/mic-send/viewport',width);
   await page.screenshot({path:`/workspace/work/chat-${width}.png`});await page.close();
  }
  for(const width of [320,390,768]){
   const guide=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await ready(guide,'http://127.0.0.1:18502');
   await send(guide,'노인이 할 수 있는 운동 추천해 줘');
   await guide.getByRole('button',{name:'수중운동 알아보기',exact:true}).waitFor();
   await guide.getByText('일반 활동 제안 · 실제 모집 프로그램 아님',{exact:true}).last().waitFor();
   const choice=await guide.getByRole('button',{name:'수중운동 알아보기',exact:true}).boundingBox();
   if(choice.height<56||choice.x<0||choice.x+choice.width>width+1)throw Error('Inaccessible idea target');
   if(width===390)await guide.screenshot({path:'/workspace/work/guidance-390.png'});
   await guide.getByRole('button',{name:'수중운동 알아보기',exact:true}).click();
   await guide.getByRole('button',{name:'서울 강서구에서 찾기',exact:true}).click();
   await guide.getByText('접수 가능 여부가 확인되지 않았거나',{exact:false}).last().waitFor();await idle(guide);
   await guide.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
   await guide.getByRole('button',{name:'처음부터 다시 찾기',exact:true}).click();await idle(guide);
   const menu=guide.getByRole('button',{name:'＋ 보조 메뉴',exact:false});
   if(await menu.getAttribute('aria-expanded')==='true')await menu.click();
   await send(guide,'근처 수영장 찾아줘');
   await guide.getByText('근처를 알려면 지역이 필요해요.',{exact:false}).waitFor();
   await guide.getByRole('button',{name:'서울 강서구에서 찾기',exact:true}).click();
   await guide.getByRole('heading',{name:'공항동문화체육센터',exact:true}).waitFor();await idle(guide);
   await guide.getByRole('link',{name:'시설 근거 공식 출처',exact:true}).waitFor();
   await guide.getByText('현재 이용 가능 여부 미확인',{exact:false}).waitFor();
   await send(guide,'강서구에서 수영 배우고 싶어');
   await guide.getByText('수영에 대해 확인한 결과예요.',{exact:false}).waitFor();
   await guide.getByRole('button',{name:'수중운동 알아보기',exact:true}).waitFor();
   await send(guide,'다른 운동도 추천해 줘');
   await guide.getByRole('button',{name:'파크골프 알아보기',exact:true}).waitFor();await idle(guide);
   await guide.getByRole('button',{name:'다른 활동 찾기',exact:true}).click();
   await guide.getByText('다른 활동',{exact:true}).last().waitFor();
   await guide.getByRole('button',{name:'그림·만들기 알아보기',exact:true}).waitFor();await idle(guide);
   await send(guide,'오전에 할 수 있는 활동은?');
   await guide.getByText('오전 선호를 기억했어요.',{exact:false}).last().waitFor();
   await send(guide,'오후에 하고 싶어요');
   await send(guide,'오후 말고 오전으로 찾아줘');
   await guide.getByText('오전 선호를 기억했어요.',{exact:false}).last().waitFor();
   if(await guide.locator('[data-testid="stException"]').count())throw Error('Guidance flow exception');
   if(await guide.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Guidance overflow');
   console.log('PASS general recommendation -> choice -> no result -> nearby facility -> program -> alternatives/time/mobile',width);
   await guide.close();
  }

  const fallback=await browser.newPage({viewport:{width:390,height:850}});await ready(fallback);
  const reported='강서구에서 어르신이 참여할 수 있는 운동을 추천해줘';
  await send(fallback,reported);
  await fallback.getByText('Gemini 연결을 이용하지 못해 기본 규칙으로 안내하고 있어요.',{exact:false}).waitFor();
  await fallback.getByRole('button',{name:'가벼운 걷기 알아보기',exact:true}).waitFor();
  await fallback.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  await fallback.getByText('연결 상태 확인',{exact:true}).click();
  await fallback.getByText('진단 코드: rate_limit',{exact:true}).waitFor();
  if((await fallback.locator('body').innerText()).includes('provider-private-canary-no-log'))throw Error('Provider error leaked');
  await fallback.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  await send(fallback,'오후요');
  await fallback.getByText('오후요',{exact:true}).waitFor();
  if(await fallback.getByText(reported,{exact:true}).count()!==1)throw Error('Original question lost');
  console.log('PASS mock Gemini SDK HTTP429 -> safe diagnostic/official fallback -> followup/history');await fallback.close();

  const probe=await browser.newPage({viewport:{width:390,height:850}});await ready(probe);
  await send(probe,'강서구 국악');await concert(probe);
  await probe.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  await probe.getByText('Gemini 모델 연결 점검',{exact:true}).click();
  await probe.getByRole('button',{name:'모델 정보 확인',exact:true}).click();
  await probe.getByText('모델 정보: metadata_ok',{exact:true}).waitFor();
  await probe.getByText('모델 목록: list_ok',{exact:true}).waitFor();
  await probe.getByText('무료 티어·잔여 한도는 미확인입니다.',{exact:false}).waitFor();
  await probe.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  if(await probe.getByText('강서구 국악',{exact:true}).count()!==1)throw Error('Model probe changed conversation');
  console.log('PASS read-only model metadata/list -> quota unverified -> conversation preserved');
  await send(probe,'강서구에서 파크골프 프로그램 찾아줘');
  await probe.getByRole('heading',{name:'서남센터 파크골프장(18홀)',exact:true}).waitFor();
  await probe.getByText('2023-04-01~2026-12-31',{exact:false}).waitFor();
  await probe.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  await probe.getByText('연결 상태 확인',{exact:true}).click();
  await probe.getByText('진단 코드: generation_not_found',{exact:true}).waitFor();
  if((await probe.locator('body').innerText()).includes('private-provider-canary'))throw Error('404 raw error leaked');
  console.log('PASS mock generation 404 -> unresolved diagnostic -> official fallback');await probe.close();

  const generation=await browser.newPage({viewport:{width:390,height:850}});await ready(generation);
  await send(generation,'강서구 국악');await concert(generation);
  await generation.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  await generation.getByText('Gemini 생성 요청 점검',{exact:true}).click();
  await generation.getByRole('button',{name:'고정 인사말로 생성 점검',exact:true}).click();
  await generation.getByText('단순 생성: ok',{exact:true}).waitFor();
  await generation.getByText('구조화 추출: generation_not_found',{exact:true}).waitFor();
  const diagBody=await generation.locator('body').innerText();
  if(diagBody.includes('private-response-canary'))throw Error('Generation probe exposed raw body');
  if(await generation.getByText('강서구 국악',{exact:true}).count()!==1)throw Error('Generation probe changed conversation');
  console.log('PASS fixed greeting success / structured 404 -> safe comparison / original dialogue');await generation.close();

  const voice=await browser.newPage({viewport:{width:390,height:850},isMobile:true,hasTouch:true});
  await ready(voice);
  await voice.getByRole('button',{name:'마이크로 말하기',exact:true}).click();
  const stop=voice.getByRole('button',{name:'말하기 끝내기',exact:true});await stop.waitFor();
  await voice.waitForTimeout(1500); // synthetic input needs >0.2s; not a silence detector
  const status=await voice.locator('[data-testid="stChatInput"]').evaluate(e=>getComputedStyle(e,'::before').content);
  if(!status.includes('듣고 있어요'))throw Error('Missing recording status');
  await stop.focus();await voice.keyboard.press('Space');
  await concert(voice);
  await voice.getByRole('button',{name:'음성 중지',exact:true}).waitFor();
  await voice.getByRole('button',{name:'답변 듣기',exact:true}).click();
  await voice.waitForFunction(()=>document.querySelector('audio[data-testid="stAudio"]')?.paused===false);
  await voice.getByRole('button',{name:'음성 중지',exact:true}).click();
  await voice.locator('audio[data-testid="stAudio"]').waitFor({state:'detached'});
  await voice.getByText('음성인식이 다르게 되었나요?',{exact:true}).click();
  await voice.getByRole('button',{name:'글자 수정하기',exact:true}).click();
  const edit=voice.getByRole('textbox',{name:'인식된 문장 수정',exact:true});await edit.waitFor();
  if(await edit.inputValue()!=='강서구에서 국악 공연을 보고 싶어요')throw Error('Transcript not editable');
  await edit.fill('이전 수정 초안');
  const composer=voice.locator('[data-testid="stChatInputTextArea"]');
  await composer.fill('작성 중인 글');
  await voice.getByRole('button',{name:'다시 말하기',exact:true}).click();
  await voice.getByText('작성 중인 글이 있어요.',{exact:false}).waitFor();
  if(await composer.inputValue()!=='작성 중인 글')throw Error('Retry erased a draft');
  if(await voice.getByRole('button',{name:'말하기 끝내기',exact:true}).count())throw Error('Retry started recording over a draft');
  await voice.getByRole('button',{name:'음성 입력으로 돌아가기',exact:true}).click();
  await voice.getByRole('button',{name:'다시 말하기',exact:true}).click();
  await stop.waitFor();await voice.waitForTimeout(1500);await stop.click();
  await voice.waitForFunction(()=>document.querySelectorAll('[data-testid="stChatMessageAvatarUser"]').length===2);
  const editButton=voice.getByRole('button',{name:'글자 수정하기',exact:true});
  if(!await editButton.isVisible()) await voice.getByText('음성인식이 다르게 되었나요?',{exact:true}).click();
  await editButton.click();
  await edit.waitFor();
  if(await edit.inputValue()!=='강서구에서 국악 공연을 보고 싶어요')throw Error('Stale transcript correction draft');
  console.log('PASS synthetic mic/keyboard stop -> mock STT -> chat/search/TTS/playback/stop/edit/retry/draft guard');await voice.close();

  for(const error of ['NotAllowedError','NotReadableError','unsupported']){
   const p=await browser.newPage({viewport:{width:390,height:850}});
   await p.addInitScript(error=>{
    if(error==='unsupported'){Object.defineProperty(navigator,'mediaDevices',{value:undefined,configurable:true});window.MediaRecorder=undefined;}
    else navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Test only',error)};
   },error);
   await ready(p);const mic=p.getByRole('button',{name:'마이크로 말하기',exact:true});if(await mic.isEnabled())await mic.click();
   await send(p,'강서구 국악');await concert(p);
   console.log('PASS microphone failure -> text search',error);await p.close();
  }
  const blocked=await browser.newPage({viewport:{width:390,height:850}});
  await blocked.addInitScript(()=>{HTMLMediaElement.prototype.play=()=>Promise.reject(new DOMException('Test only','NotAllowedError'))});
  await ready(blocked);await send(blocked,'강서구 국악');await concert(blocked);
  await blocked.getByRole('button',{name:'답변 듣기',exact:true}).click();
  await blocked.locator('#ieum-listen').click();
  await blocked.getByText('소리를 재생하지 못했어요.',{exact:false}).waitFor();
  await send(blocked,'다른 시간');await blocked.getByRole('button',{name:'오후',exact:true}).waitFor();
  console.log('PASS rejected playback keeps text/followup');await blocked.close();

  const upload=await browser.newPage({viewport:{width:390,height:850}});await ready(upload);
  await upload.getByRole('button',{name:'＋ 보조 메뉴',exact:false}).click();
  await upload.getByText('음성파일 올리기',{exact:true}).click();
  const wav=Buffer.alloc(44+16000);wav.write('RIFF',0);wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(16000,24);wav.writeUInt32LE(32000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(16000,40);for(let i=44;i<wav.length;i+=2)wav.writeInt16LE(3000*Math.sin(i*.17),i);
  await upload.locator('input[type=file]').setInputFiles({name:'question.wav',mimeType:'audio/wav',buffer:wav});
  await concert(upload);
  await upload.waitForFunction(()=>document.querySelector('[data-testid=stPopoverButton]')?.getAttribute('aria-expanded')==='false');
  console.log('PASS plus menu upload -> automatic chat');await upload.close();
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
