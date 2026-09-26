import json,os,re,collections
OK=re.compile(r'[\x00-\x7f -ÿ가-힣ᄀ-ᇿ㄰-㆏一-鿿豈-﫿 -⯿　-〿㈀-㋿＀-￯①-⓿■-◿-\s]')
inv=json.load(open('../inventory.json'))
bad={}
for x in inv:
    if x['ext']!='pdf': continue
    d='cache/'+x['sha256'][:12]+'/'
    pages=[]
    for f in sorted(os.listdir(d)):
        if not re.match(r'p\d{4}\.md$',f): continue
        t=open(d+f,encoding='utf-8').read()
        weird=sum(1 for ch in t if not OK.match(ch))
        hang=len(re.findall(r'[가-힣]',t))
        if weird>=30 and weird>hang*0.3: pages.append(int(f[1:5]))
    if pages: bad[x['saved_path']]=pages; print(len(pages),x['saved_path'][-65:])
json.dump(bad,open('bad_pages.json','w'),ensure_ascii=False)
print('total',sum(len(v) for v in bad.values()))
