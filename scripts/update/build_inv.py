import json,os
s=json.load(open(os.path.expanduser('~/epc_out/state.json')))['records']
by={}
for k,v in s.items():
    if not v.get('saved_path') or not v.get('sha256'): continue
    p=os.path.expanduser('~/epc_out/'+v['saved_path'])
    if not os.path.exists(p): continue
    h=v['sha256']; e=by.setdefault(h,dict(saved_path=v['saved_path'],sha256=h,bytes=v.get('bytes'),ext=v['saved_path'].rsplit('.',1)[1].lower(),labels=[],file_urls=[],posts=[],collector_ids=[],declared_bytes_match=v.get('declared_bytes_match')))
    for f,val in (('labels',v.get('title')),('file_urls',v.get('url')),('posts',v.get('parent_url')),('collector_ids',v.get('id'))):
        if val and val not in e[f]: e[f].append(val)
inv=sorted(by.values(),key=lambda x:x['saved_path'])
json.dump(inv,open(os.path.expanduser('~/inventory.json'),'w'),ensure_ascii=False,indent=1)
print(len(inv))
