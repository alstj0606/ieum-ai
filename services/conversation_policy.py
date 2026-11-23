"""Current-message priority. A pending form is context, never an input trap."""
import re

GENERAL={'chat','explore','home','howto'}
YES={'응','네','예','맞아','맞아요','그래','그래요','좋아','좋아요'}


def compact(text):return re.sub(r'\s+','',text).rstrip('.!?？')

def search_request(text):
    c=compact(text)
    local=any(x in c for x in ('근처','우리동네','주변','배울곳','어디서','동네에도','동네에서'))
    action=any(x in c for x in ('찾','있','알려','추천','배우'))
    named=any(x in c for x in ('프로그램','강좌','강습','수영장','시설','문화센터'))
    return (local and action) or (named and action) or any(x in c for x in ('인터넷검색다시','다시검색'))


def counselling_request(text):
    c=compact(text)
    if search_request(text):return None
    if any(x in c for x in ('처음배우면','처음배우려','어떻게시작','시작방법','시작하는방법','쉬운건','준비물','잘못춰','잘못그려')):return 'howto'
    if '집에서' in c and any(x in c for x in ('취미','혼자','할수','즐길')):return 'home'
    if any(x in c for x in ('심심','취미가없','사람들이랑','사람들만나','친구를','뭘하면','뭘해야','돈안들','관심사','추천받')):return 'explore'
    return None


def choose_route(text,previous,request,plan,rule):
    if search_request(text):return 'search'
    current=counselling_request(text)
    if current:return current
    if rule=='followup':return rule
    # Validated model intent may interrupt any pending location question.
    if plan and plan['route'] in GENERAL:return plan['route']
    # Only actual slot answers continue a previous search. An unrelated question
    # doesn't become a search merely because pending='region'.
    slot_fields=set(request['update_fields'])|set(request['clear_fields'])
    if previous.get('search_requested') and slot_fields and not ('?' in text or '？' in text):return 'search'
    if plan:return plan['route']
    return rule


def phase(state):
    route=state.get('conversation_route')
    if state.get('pending') in {'region','web_location','web_dong','location_confirmation'}:return 'location_input'
    if state.get('web') or state.get('results') or state.get('references'):return 'search_results'
    if route=='howto':return 'getting_started'
    if route in {'home','explore'}:return 'hobby_recommendation' if state.get('ideas') else 'counselling'
    if route=='followup':return 'refinement'
    return 'programme_search' if route=='search' else 'counselling'
