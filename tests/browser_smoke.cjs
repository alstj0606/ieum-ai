// Optional browser test. Mock API server only; not a real OpenAI or iPad test.
const {chromium} = require('playwright');

async function ready(page, url) {
  await page.goto(url);
  await page.getByRole('textbox', {name: '어떤 활동을 하고 싶으세요?'}).waitFor();
}

async function main() {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    headless: true, args: ['--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
  });
  try {
    for (const width of [320, 390, 768]) {
      const page = await browser.newPage({viewport: {width, height: 900}, isMobile: true, hasTouch: true});
      await ready(page, 'http://127.0.0.1:18502');
      await page.getByRole('textbox').fill('수영 처음인데 어디서 배워요?');
      await page.getByRole('button', {name: '프로그램 찾아보기', exact: true}).click();
      await page.getByRole('button', {name: '서울 강서구에서 찾기', exact: true}).click();
      await page.getByText('현재 확인한 강서구 자료에서는 조건에 맞는 신청 가능한 활동을 찾지 못했어요.', {exact: false}).first().waitFor();
      await page.getByRole('button', {name: '초보 수영 찾기', exact: true}).click();
      await page.getByRole('heading', {name: '처음 배우는 수영 (가상 프로그램)', exact: true}).waitFor();
      const metrics = await page.evaluate(() => ({
        width: innerWidth, scroll: document.documentElement.scrollWidth,
        overflow: [...document.querySelectorAll('.stMain h1,.stMain h2,.stMain h3,.stMain p,.stMain textarea,.stMain button')]
          .filter(e => {const r=e.getBoundingClientRect(); return r.width>0 && (r.right>innerWidth+1 || r.left<0)}).length,
        heights: [...document.querySelectorAll('.stButton button,.stFormSubmitButton button')]
          .filter(e => e.getBoundingClientRect().height>0).map(e => e.getBoundingClientRect().height),
      }));
      if (metrics.scroll>width || metrics.overflow || metrics.heights.some(h=>h<64)) throw Error(JSON.stringify(metrics));
      console.log('PASS no-key dialogue/example/mobile layout', width);
      await page.close();
    }

    const page = await browser.newPage({viewport:{width:390,height:900},isMobile:true,hasTouch:true});
    await ready(page, 'http://127.0.0.1:18504');
    await page.getByText('🎤 말로 입력하기', {exact:true}).click();
    // File fallback -> mocked STT -> visible editable text -> mocked LLM -> real JSON cards.
    const wav = Buffer.alloc(44+16000);
    wav.write('RIFF',0);wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);
    wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);
    wav.writeUInt32LE(16000,24);wav.writeUInt32LE(32000,28);wav.writeUInt16LE(2,32);
    wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(16000,40);
    for(let i=44;i<wav.length;i+=2) wav.writeInt16LE(3000*Math.sin(i*.17),i);
    await page.locator('input[type=file]').setInputFiles({name:'question.wav',mimeType:'audio/wav',buffer:wav});
    await page.getByRole('button',{name:'음성을 글로 바꾸기',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('textarea')?.value==='강서구에서 국악 공연을 보고 싶어요');
    await page.getByRole('textbox').fill('강서구 국악 관람');
    await page.getByRole('button',{name:'프로그램 찾아보기',exact:true}).click();
    await page.getByRole('heading',{name:'1. 2026 제27회 강서국악한마당',exact:true}).waitFor();
    await page.getByRole('link',{name:'공식 안내·신청 페이지 열기',exact:true}).first().waitFor();
    const links = await page.getByRole('link',{name:'공식 안내·신청 페이지 열기',exact:true}).all();
    if(links.length!==1 || !(await links[0].getAttribute('href')).includes('cultureSn=268')) throw Error('Incorrect official link');
    await page.getByRole('button',{name:'이 활동 신청 방법',exact:true}).click();
    await page.getByText('아직 신청·예약·결제가 완료된 것은 아니에요.',{exact:false}).first().waitFor();
    await page.getByRole('button',{name:'답변 듣기',exact:true}).click();
    const audio=page.locator('audio[data-testid="stAudio"]');
    await audio.waitFor();
    if(await audio.evaluate(a=>a.autoplay)) throw Error('Autoplay unexpectedly enabled');
    await audio.evaluate(a=>a.play()); // synthetic tone only, not speech quality
    await page.getByRole('button',{name:'음성 중지',exact:true}).click();
    await audio.waitFor({state:'detached'});
    console.log('PASS mock SDK STT -> edit -> dialogue -> official facts -> application -> audio/stop');
    await page.close();

    const denied = await browser.newPage({viewport:{width:390,height:900}});
    await denied.addInitScript(()=>{
      navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Test denied','NotAllowedError')};
    });
    await ready(denied,'http://127.0.0.1:18504');
    await denied.getByText('🎤 말로 입력하기',{exact:true}).click();
    await denied.getByRole('button',{name:'Record',exact:true}).click();
    await denied.getByRole('textbox').fill('강서구 국악');
    await denied.getByRole('button',{name:'프로그램 찾아보기',exact:true}).click();
    await denied.getByRole('heading',{name:'1. 2026 제27회 강서국악한마당',exact:true}).waitFor();
    console.log('PASS microphone permission rejection preserves text flow (simulated NotAllowedError)');
    await denied.close();

    const recorded = await browser.newPage({viewport:{width:390,height:900},isMobile:true,hasTouch:true});
    await ready(recorded,'http://127.0.0.1:18504');
    await recorded.getByText('🎤 말로 입력하기',{exact:true}).click();
    await recorded.getByRole('button',{name:'Record',exact:true}).click();
    await recorded.waitForFunction(()=>{
      const timer=document.querySelector('[data-testid="stAudioInputWaveformTimeCode"]');
      return timer && timer.textContent!=='00:00';
    });
    await recorded.getByRole('button',{name:'Stop recording',exact:true}).click();
    await recorded.getByRole('button',{name:'음성을 글로 바꾸기',exact:true}).click();
    await recorded.waitForFunction(()=>document.querySelector('textarea')?.value==='강서구에서 국악 공연을 보고 싶어요');
    console.log('PASS synthetic microphone record/stop -> mock transcription (not a real device/recognition test)');
    await recorded.close();

    const unsupported = await browser.newPage({viewport:{width:390,height:900}});
    await unsupported.addInitScript(()=>{
      Object.defineProperty(navigator,'mediaDevices',{value:undefined,configurable:true});
      window.MediaRecorder=undefined;
    });
    await ready(unsupported,'http://127.0.0.1:18504');
    await unsupported.getByText('🎤 말로 입력하기',{exact:true}).click();
    const recordButton=unsupported.getByRole('button',{name:'Record',exact:true});
    if(await recordButton.isEnabled()) await recordButton.click();
    await unsupported.getByRole('textbox').fill('강서구 국악');
    await unsupported.getByRole('button',{name:'프로그램 찾아보기',exact:true}).click();
    await unsupported.getByRole('heading',{name:'1. 2026 제27회 강서국악한마당',exact:true}).waitFor();
    console.log('PASS unavailable media APIs preserve text fallback (simulated browser)');
    await unsupported.close();
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exit(1)});
