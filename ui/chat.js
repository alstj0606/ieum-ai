// Fixed UI code only. Never interpolate a transcript or provider response here.
(() => {
  if (window.ieumChatObserver) window.ieumChatObserver.disconnect();
  const names = {
    stChatInputMicButton:'마이크로 말하기', stChatInputSubmitButton:'질문 전송',
    stChatInputCancelButton:'녹음 취소', stChatInputApproveButton:'말하기 끝내기'
  };
  const update = () => {
    const root=document.querySelector('[data-testid="stChatInput"]');
    if(!root) return;
    for(const [id,name] of Object.entries(names)) {
      const b=root.querySelector(`[data-testid="${id}"]`);
      if(b && b.getAttribute('aria-label')!==name) {b.setAttribute('aria-label',name);b.title=name;}
    }
    const input=root.querySelector('textarea');
    const mic=root.querySelector('[data-testid="stChatInputMicButton"]');
    if(input && mic) {
      // Guard the actual control as well as hiding it while a draft exists.
      if(input.value.trim() && !mic.dataset.draftDisabled) {
        mic.dataset.wasDisabled=mic.disabled?'1':'0';mic.dataset.draftDisabled='1';mic.disabled=true;
      } else if(!input.value.trim() && mic.dataset.draftDisabled) {
        mic.disabled=mic.dataset.wasDisabled==='1';delete mic.dataset.draftDisabled;
      }
      if(!root.querySelector('#ieum-voice-back')) {
        const back=document.createElement('button');
        back.id='ieum-voice-back';back.type='button';back.textContent='🎤';
        back.setAttribute('aria-label','음성 입력으로 돌아가기');back.title='글을 비우고 음성 입력으로 돌아가기';
        back.onclick=()=>{
          const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
          const current=root.querySelector('textarea');
          if(!current)return;
          setter.call(current,'');current.dispatchEvent(new Event('input',{bubbles:true}));
          // Returning to voice does not begin recording. A second deliberate press is required.
          setTimeout(()=>root.querySelector('[data-testid="stChatInputMicButton"]')?.focus(),0);
        };
        mic.parentElement.prepend(back);
      }
    }
  };
  window.ieumChatObserver=new MutationObserver(update);
  window.ieumChatObserver.observe(document.body,{childList:true,subtree:true});
  if(window.ieumInputHandler) document.removeEventListener('input',window.ieumInputHandler);
  window.ieumInputHandler=update;
  document.addEventListener('input',update);
  update();
})();
// Restore the latest answer when a virtual keyboard changes the visible viewport.
(() => {
  if(window.ieumViewportHandler) {
    window.visualViewport?.removeEventListener('resize',window.ieumViewportHandler);
    window.removeEventListener('resize',window.ieumViewportHandler);
  }
  window.ieumViewportHandler=()=>{
    clearTimeout(window.ieumViewportTimer);
    window.ieumViewportTimer=setTimeout(()=>{
      if(document.activeElement?.matches('[data-testid="stChatInputTextArea"]')) {
        [...document.querySelectorAll('[id^="latest-reply-"]')].at(-1)?.scrollIntoView({block:'start'});
      }
    },300);
  };
  window.visualViewport?.addEventListener('resize',window.ieumViewportHandler);
  window.addEventListener('resize',window.ieumViewportHandler);
})();
