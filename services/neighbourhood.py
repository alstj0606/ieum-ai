"""Explicit location slots; no GPS, geocoding, or administrative-dong guessing."""
import re

CITIES=('서울','부산','인천','대전','대구','울산','광주','세종','창원','부천')

def location_from(conditions,text='',previous=None):
 previous=previous or {};region=conditions.get('region') or ''
 city_match=re.search(r'(?:^|\s)([가-힣]{2,8})시(?:에서|에|로|요|\s|$)',text)
 city={'서울특별':'서울','부산광역':'부산','인천광역':'인천','대전광역':'대전','광주광역':'광주','울산광역':'울산','세종특별자치':'세종'}.get(city_match.group(1),city_match.group(1)) if city_match else next((c for c in CITIES if re.search(r'(?:^|\s)'+c+r'(?:특별시|광역시|시)?(?:에서|에|로|요|\s|$)',text)),None)
 city=city or next((c for c in CITIES if region.startswith(c)),None)
 area=re.search(r'([가-힣]{2,8}구)',region)
 district=area.group(1) if area else None
 dong=conditions.get('neighbourhood')
 explicit_dong=re.search(r'(?:^|\s)([가-힣]{2,10}\d{0,2}동)(?:에|에서|근처|요|\s|$)',text)
 if explicit_dong and not explicit_dong.group(1).endswith(('운동','활동','이동')):dong=explicit_dong.group(1)
 if not city and previous.get('district')==district and district:city=previous.get('city')
 if not city and not region:city=previous.get('city');district=previous.get('district')
 return dict(city=city,district=district,neighbourhood=dong)

def question(location):
 if not location.get('city'):
  return (location.get('neighbourhood')+'은 ' if location.get('neighbourhood') else '')+'어느 시·구인가요? 동 이름이 같은 곳이 있어 한 번 확인할게요.'
 if location.get('neighbourhood') and not location.get('district'):return location['city']+'의 어느 구에 있는 '+location['neighbourhood']+'인가요?'
 return None

def location_label(location):return ' '.join(location[k] for k in ('city','district','neighbourhood') if location.get(k))
