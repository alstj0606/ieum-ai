"""Small, factual live-result cards; no provider text/HTML is rendered as HTML."""
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo
import streamlit as st
from services.web_search import ERRORS,recruitment_status
from services.date_display import display_date_text


def checked(value):
 try:return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y.%m.%d %H:%M KST')
 except (ValueError,TypeError):return '확인 필요'

def fact(label,value):st.markdown('**'+label+'** · '+display_date_text(str(value or '확인 필요')).replace('~',r'\~'))

def render(state,*,on_select,on_send,on_cache):
 web=state['web'];rows=web.get('rows',[]);selected=web.get('selected_id')
 if web.get('cache_hit') and not state.get('life_mode'):st.caption('검색 목록 재사용 · 출처별 본문 확인 결과를 표시해요.')
 if rows:st.caption('공식 출처 확인 '+checked(web['checked_at'])+' · 신청 전 모집 상태를 확인해 주세요.')
 for row in rows:
  if selected and selected!=row['id']:continue
  detail=selected==row['id'];status=recruitment_status(row)
  with st.container(key='web_card_'+row['id']):
   st.subheader(row['name']);st.caption(status+' · '+row['match_label'])
   fact('장소',row['facility']);st.caption(row['relation'])
   fact('요일·시간',row['schedule'] or (display_date_text(row['starts_at']) if row['starts_at'] else None))
   fact('비용',row['fee_text'] or ('무료' if row['fee_amount']==0 else f"{row['fee_amount']:,}원 · 과금 단위 확인 필요" if row['fee_amount'] is not None else None))
   if detail:
    st.markdown('#### 장소와 참여 대상');fact('운영 기관',row['institution']);fact('주소',row['address']);fact('대상',row['target'])
    st.markdown('#### 모집과 신청');fact('접수 기간',row['registration_text']);fact('모집 상태',status)
    fact('신청 방법',row['registration_method']);fact('준비 사항',row['preparation']);fact('다음 접수 일정','미정')
    st.caption('게시일과 운영일은 달라요. 다음 모집을 추정하지 않아요.')
    if row['published_at']:fact('페이지 게시일',row['published_at'])
    st.caption('외부 공식 사이트가 새 창으로 열려요. 이음 AI 창을 유지하고 돌아오세요. 신청 완료를 확인한 것은 아니에요.')
    st.link_button('공식 홈페이지',row['official_url'],use_container_width=True)
    if row['application_url'] and status not in ('접수 마감','운영 종료'):
     st.link_button('공식 '+str(row['action'])+' 페이지',row['application_url'],use_container_width=True)
     st.caption('페이지 연결만 확인했어요. 모집·로그인·참가 자격은 공식 사이트에서 확인해 주세요.')
    else:st.caption('신청 경로 확인 필요' if not row['application_url'] else status+' · 신청 가능하다고 안내하지 않아요.')
    if row['address']:st.link_button('주소로 길 찾기', 'https://map.naver.com/p/search/'+quote(row['address'],safe=''),use_container_width=True)
    st.caption('공식 출처 · '+row['official_url']+' · 확인 '+checked(row['verified_at']))
   else:st.button('자세히 보기',key='web_detail_'+row['id'],on_click=on_select,args=(row['id'],),use_container_width=True)
   if row['phone']:st.link_button('전화하기 · '+row['phone'],'tel:'+row['phone'].replace('-',''),use_container_width=True)
   else:st.caption('문의처 확인 필요')
   st.button('다른 활동 보기',key='web_other_'+row['id'],on_click=on_send,args=('이건 별로예요',),use_container_width=True)
 if web.get('references'):
  with st.expander('검색 출처 · 프로그램으로 확인하지 못한 자료'):
   for i,ref in enumerate(web['references']):
    st.write(ref['title']);st.caption(ref['note'])
    if ref.get('published_at'):st.caption('검색엔진 표시 게시 정보 · '+ref['published_at']+' · 운영일 아님')
    st.link_button('공식 근거 페이지' if ref['official'] else '일반 검색 결과 · 공식 미확인',ref['url'],use_container_width=True)
 if state.get('pending')=='web_expand':
  st.write('다른 동네까지 범위를 넓혀 찾아볼까요?')
  st.button('네, 다른 동네도 찾아주세요',key='web_expand_yes',on_click=on_send,args=('네, 다른 동네도 찾아주세요',),use_container_width=True)
  st.button('아니요, 이 동네만 볼게요',key='web_expand_no',on_click=on_send,args=('아니요, 이 동네만 볼게요',),use_container_width=True)
 if not rows:st.button('저장 자료로 찾아보기',key='web_cache',on_click=on_cache,use_container_width=True)
 st.button('인터넷 검색 다시 하기',key='web_retry',on_click=on_send,args=('인터넷 검색 다시 하기',),use_container_width=True)
