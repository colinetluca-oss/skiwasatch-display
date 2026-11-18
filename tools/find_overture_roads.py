import fsspec, pyarrow.parquet as pq, pyarrow as pa, json, sys
from concurrent.futures import ThreadPoolExecutor
BB=(-112.02,40.42,-111.33,40.86)
import requests, io
S=requests.Session()
class RF(io.RawIOBase):
    def __init__(s,url):
        s.url=url; s.pos=0; s.size=int(S.head(url,timeout=60).headers['Content-Length'])
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.pos
    def seek(s,o,w=0):
        s.pos = o if w==0 else s.pos+o if w==1 else s.size+o; return s.pos
    def readinto(s,b):
        if s.pos>=s.size: return 0
        end=min(s.size,s.pos+len(b))-1
        for t in range(4):
            try:
                d=S.get(s.url,headers={'Range':f'bytes={s.pos}-{end}'},timeout=120).content; break
            except Exception:
                if t==3: raise
        b[:len(d)]=d; s.pos+=len(d); return len(d)
def fopen(url): return io.BufferedReader(RF(url), buffer_size=1<<20)
base='https://s3.us-west-2.amazonaws.com/overturemaps-us-west-2/'
keys=open('ov_keys.txt').read().split()
def stats_hit(md, rg, names):
    r=md.row_group(rg); s={}
    for i in range(r.num_columns):
        c=r.column(i); p=c.path_in_schema
        if p in names and c.statistics is not None and c.statistics.has_min_max: s[p]=(c.statistics.min,c.statistics.max)
    try:
        return not (s['bbox.xmax'][0]>BB[2] or s['bbox.xmin'][1]<BB[0] or s['bbox.ymax'][0]>BB[3] or s['bbox.ymin'][1]<BB[1])
    except KeyError: return True
def scan(k):
    f=fopen(base+k); pf=pq.ParquetFile(f); md=pf.metadata
    rgs=[i for i in range(md.num_row_groups) if stats_hit(md,i,{'bbox.xmin','bbox.xmax','bbox.ymin','bbox.ymax'})]
    return k,rgs
with ThreadPoolExecutor(16) as ex: res=list(ex.map(scan,keys))
hits=[(k,r) for k,r in res if r]
print(len(hits), sum(len(r) for k,r in hits)); json.dump(hits,open('ov_hits.json','w'))
