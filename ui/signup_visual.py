"""Inert label diagrams, not official screenshots or an embedded registration form."""
from html import escape

# Only relative locations reported by the user on 2026-11-11. No pixel coordinates.
CONTEXTS = {
    'signup_open': '이음 AI에서 공식 사이트를 여는 안내',
    'signup_menu': '공식 사이트 상단 메뉴',
    'signup_id': '공식 로그인 화면 아래쪽',
    'signup_terms': '본인인증 화면의 회원가입약관',
    'signup_verify': '본인인증 화면의 안심본인 인증(휴대폰 인증) 영역',
}


def visual_guide_html(step):
    """Show one known step. No inputs, clickable imitation controls, scripts or frames."""
    context = CONTEXTS.get(step['step_id'])
    if context is None:
        return ''  # Unverified stages never acquire a plausible-looking illustration.
    label = step['button_label'] or '공식 신청 사이트 열기 → (이음 AI 버튼)'
    return f'''<section class="ieum-signup-visual" aria-labelledby="signup-visual-title"
      data-guide-step="{escape(step['step_id'], quote=True)}">
      <h4 id="signup-visual-title">버튼 찾기 예시 · 실제 사이트 아님</h4>
      <p>{escape(context)}</p>
      <div class="ieum-visual-target">
        <span class="ieum-visual-arrow" aria-hidden="true">↓</span>
        <strong>{escape(label)}</strong>
      </div>
      <p>공식 화면의 캡처가 아닌 이름 중심의 구조도예요. 실제 배치·크기와 달라요.</p>
      <p>여기서는 연습만 해요. 실제 선택과 인증은 공식 사이트에서 직접 해 주세요.</p>
    </section>'''
