// Fixed UI code only. Never interpolate a transcript or provider response here.
(() => {
  if (window.ieumChatObserver) window.ieumChatObserver.disconnect();
  const names = {
    stChatInputSubmitButton:'질문 전송',
    stChatInputCancelButton:'녹음 취소', stChatInputApproveButton:'말하기 끝내기'
  };
  const update = () => {
    const root=document.querySelector('[data-testid="stChatInput"]');
    if(!root) return;
    for(const [id,name] of Object.entries(names)) {
      const b=root.querySelector(`[data-testid="${id}"]`);
      if(b && b.getAttribute('aria-label')!==name) {b.setAttribute('aria-label',name);b.title=name;}
    }
    const retry=document.getElementById('ieum-retry-voice');
    if(retry) retry.onclick=()=>{
      const status=document.getElementById('ieum-retry-status');
      const input=root.querySelector('textarea');
      const mic=root.querySelector('[data-testid="stChatInputMicButton"]');
      if(input?.value.trim()) {
        status.textContent='작성 중인 글이 있어요. 먼저 보내거나 입력창의 작은 마이크로 음성 입력으로 돌아가세요.';
      } else if(!mic || mic.disabled) {
        status.textContent='녹음 중이면 말하기 끝내기를 누르세요. 마이크가 안 되면 글로 질문해 주세요.';
      } else {
        document.querySelectorAll('audio').forEach(audio=>audio.pause());
        status.textContent='마이크를 준비해요. 권한 안내가 나오면 허용해 주세요. 안 되면 글로 질문해 주세요.';
        mic.scrollIntoView({block:'nearest'});mic.focus();mic.click();
      }
    };
    const input=root.querySelector('textarea');
    const mic=root.querySelector('[data-testid="stChatInputMicButton"]');
    if(input && mic) {
      const hasText=!!input.value.trim();
      root.dataset.hasText=String(hasText);
      const name=hasText?'음성 입력으로 돌아가기':'마이크로 말하기';
      mic.setAttribute('aria-label',name);mic.title=name;
      // Reuse the native control, never insert a sibling into React-owned DOM.
      if(!mic.dataset.ieumBound) {
        mic.dataset.ieumBound='1';
        mic.addEventListener('click',event=>{
          const owner=mic.closest('[data-testid="stChatInput"]');
          const current=owner?.querySelector('textarea');
          if(current?.value.trim()) {
            event.preventDefault();event.stopImmediatePropagation();
            const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
            setter.call(current,'');current.dispatchEvent(new Event('input',{bubbles:true}));
            setTimeout(()=>mic.focus(),0);
          } else {
            document.querySelectorAll('audio').forEach(audio=>audio.pause());
          }
        },true);
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
