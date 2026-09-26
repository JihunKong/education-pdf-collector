import re,html,subprocess,json,sys,time
UA='education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'
def page(site,mi,p,listCo=50,bbsId=''):
    u=f'https://www.jge.go.kr/{site}/na/ntt/selectNttList.do?mi={mi}&currPage={p}&listCo={listCo}'+(f'&bbsId={bbsId}' if bbsId else '')
    t=subprocess.run(['curl','-sS','-m','40','-A',UA,u],capture_output=True).stdout.decode('utf-8','replace')
    out=[]
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>',t,re.S):
        a=re.search(r'data-id="(\d+)"[^>]*title="([^"]*)"',r)
        if not a: continue
        tds=[re.sub(r'<[^>]+>|\s+',' ',x).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',r,re.S)]
        d=next((x for x in tds if re.fullmatch(r'\d{4}\.\d{2}\.\d{2}',x)),'')
        out.append({'nttSn':a.group(1),'title':html.unescape(a.group(2)).strip(),'date':d,'cols':[x for x in tds if x][:6],'url':f'https://www.jge.go.kr/{site}/na/ntt/selectNttInfo.do?mi={mi}&nttSn={a.group(1)}'})
    return out
if __name__=='__main__':
    r=page(sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]) if len(sys.argv)>4 else 50)
    print(len(r)); [print(x['date'],x['nttSn'],x['title'][:60]) for x in r[:3]+r[-2:]]
