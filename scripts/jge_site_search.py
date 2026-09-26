#!/usr/bin/env python3
"""Query the public site search of the Jeonnam education office (www.jge.go.kr).

Returns attachment or post results (title, post URL, board path, date) for one query.
Only the public search form is used; no login, cookies or hidden endpoints.
The search engine does not match Korean words written without spaces, so pass
space-separated queries (e.g. "2030교실 수업맛집 가이드맵").
"""
import html, json, re, subprocess, sys, urllib.parse

UA = 'education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'

def search(q, menu='첨부파일', field='@title', rf='@import', nh=20):
    data = urllib.parse.urlencode({'qt': q, 'menu': menu, 'section': menu, 'field': field, 'rf': rf,
                                   'nh': nh, 'st': 1, 'searchType': '2', 'adv': '0', 'sw': '0'})
    r = subprocess.run(['curl', '-sS', '-m', '30', '-A', UA, '-X', 'POST', '-H',
                        'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
                        '--data', data, 'https://www.jge.go.kr/search/front/Search.jsp'], capture_output=True)
    t = r.stdout.decode('utf-8', 'replace'); out = []
    for m in re.finditer(r'<dl class="C_Cts">(.*?)</dl>', t, re.S):
        b = m.group(1); a = re.search(r'<a href="([^"]+)" title="([^"]*)"', b)
        if not a: continue
        cite = re.search(r'<cite class="txt3">(.*?)</cite>', b, re.S)
        c = re.sub(r'<[^>]+>', '', cite.group(1)) if cite else ''
        date = re.search(r'\[(\d{4}\.\d{2}\.\d{2})\]', c)
        out.append({'title': html.unescape(a.group(2)), 'url': html.unescape(a.group(1)),
                    'board': re.sub(r'\s+', ' ', c.split('[')[0]).strip(), 'date': date.group(1) if date else ''})
    total = re.search(r'id="Result_' + menu + r'">.*?<span class="fGun">([\d,]+)</span>', t, re.S)
    return {'q': q, 'menu': menu, 'total': total.group(1) if total else '0', 'results': out}

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit('usage: jge_site_search.py "검색어" [첨부파일|게시판]')
    print(json.dumps(search(sys.argv[1], *(sys.argv[2:3] or ['첨부파일'])), ensure_ascii=False, indent=1))
