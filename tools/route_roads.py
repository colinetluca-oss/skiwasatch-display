import pyarrow.parquet as pq, shapely, shapely.ops, numpy as np, json, math, heapq
from collections import defaultdict
from PIL import Image, ImageDraw
M=json.load(open('dem/meta.json')); W,H=M['w'],M['h']
def px(lon,lat):
    n=2**M['z']*256; x=(lon+180)/360*n; r=math.radians(lat); y=(1-math.log(math.tan(r)+1/math.cos(r))/math.pi)/2*n
    return x-M['x0'], y-M['y0']
K=math.cos(math.radians(40.65))
def mlen(cs): return sum(math.hypot((b[0]-a[0])*K,b[1]-a[1]) for a,b in zip(cs[:-1],cs[1:]))*111000
rows=pq.read_table('roads_raw.parquet').to_pylist()
SPEED={'motorway':105,'motorway_link':55,'trunk':80,'trunk_link':50,'primary':65,'primary_link':45,'secondary':55,'secondary_link':40,'tertiary':45,'tertiary_link':35,'residential':35,'unclassified':40,'living_street':20}
edges=[]; adj=defaultdict(list); nodepos={}
for r in rows:
    g=shapely.from_wkb(r['geometry'])
    if g.geom_type!='LineString': continue
    cons=sorted(r['connectors'] or [], key=lambda c:c['at'])
    r['_g']=g
    if r['class'] not in SPEED or len(cons)<2: continue
    for a,b in zip(cons[:-1],cons[1:]):
        if b['at']<=a['at']: continue
        sub=shapely.ops.substring(g,a['at'],b['at'],normalized=True)
        cs=list(sub.coords)
        if len(cs)<2: continue
        L=mlen(cs); e=len(edges); edges.append((cs,r['class'],(r['names'] or {}).get('primary')))
        w=L/(SPEED[r['class']]/3.6)
        adj[a['connector_id']].append((b['connector_id'],w,e)); adj[b['connector_id']].append((a['connector_id'],w,e))
        nodepos[a['connector_id']]=cs[0]; nodepos[b['connector_id']]=cs[-1]
ids=list(nodepos); P=np.array([nodepos[i] for i in ids])
def nearest(lon,lat,ok=None):
    d=np.hypot((P[:,0]-lon)*K,P[:,1]-lat); order=np.argsort(d)
    for i in order[:500]:
        if ok is None or ok(ids[i]): return ids[i]
def dijkstra(src):
    dist={src:0}; prev={}; pq_=[(0,src)]
    while pq_:
        d,u=heapq.heappop(pq_)
        if d>dist[u]: continue
        for v,w,e in adj[u]:
            nd=d+w
            if nd<dist.get(v,1e18): dist[v]=nd; prev[v]=(u,e); heapq.heappush(pq_,(nd,v))
    return dist,prev
home=nearest(-111.820,40.737)
print('home node at', nodepos[home], [edges[e][2] for _,_,e in adj[home]])
dist,prev=dijkstra(home)
def major_node(n): return any(edges[e][1] in ('secondary','tertiary','primary','trunk') for _,_,e in adj[n])
DEST={'alta':(-111.638,40.588),'snowbird':(-111.657,40.581),'solitude':(-111.592,40.620),'brighton':(-111.583,40.598),'park':(-111.508,40.651)}
SEGS=json.load(open('hand_segs.json'))
ROUTE={'alta':['foothill','i215','wasatch','lccLow','lccUp'],'snowbird':['foothill','i215','wasatch','lccLow'],'solitude':['foothill','i215','bccLow'],'brighton':['foothill','i215','bccLow','bccUp'],'park':['foothill','i80','sr224']}
def dpoly(pt,poly):
    x,y=pt[0]*K,pt[1]; best=1e9
    for (ax,ay),(bx,by) in zip(poly[:-1],poly[1:]):
        ax*=K;bx*=K; dx,dy=bx-ax,by-ay; t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy+1e-18)))
        best=min(best,math.hypot(ax+t*dx-x,ay+t*dy-y))
    return best
group_edges=defaultdict(set); info={}
for rid,(lo,la) in DEST.items():
    t=nearest(lo,la,major_node); path=[]; n=t
    while n!=home: u,e=prev[n]; path.append(e); n=u
    path.reverse()
    mins=dist[t]/60; L=sum(mlen(edges[e][0]) for e in path)/1609
    names=[]; [names.append(edges[e][2]) for e in path if edges[e][2] and (not names or names[-1]!=edges[e][2])]
    info[rid]=(round(mins),round(L,1)); print(rid, round(mins),'min free-flow est', round(L,1),'mi', ' > '.join(names[:14]))
    for e in path:
        cs=edges[e][0]; mid=cs[len(cs)//2]
        g=min(ROUTE[rid], key=lambda k: dpoly(mid,SEGS[k]))
        group_edges[g].add(e)
# merge edges per group into uv polylines
out={}
for g,es in group_edges.items():
    out[g]=[[[round(px(*c)[0]/W,5),round(px(*c)[1]/H,5)] for c in shapely.simplify(shapely.LineString(edges[e][0]),0.00002).coords] for e in es]
json.dump(out,open('routes.json','w')); json.dump(info,open('route_info.json','w'))
# ---------- background road network overlay (2x supersampled, then downsized) ----------
TW=4096; TH=round(H*TW/W); S=2
ov=Image.new('RGBA',(TW*S,TH*S),(0,0,0,0)); dr=ImageDraw.Draw(ov)
STY=[ ({'service','living_street'},(255,214,160,40),1),
      ({'residential','unclassified'},(255,212,155,70),1),
      ({'tertiary','tertiary_link','secondary_link'},(255,210,150,110),2),
      ({'secondary','primary','primary_link','trunk_link','motorway_link'},(255,206,145,150),3),
      ({'trunk','motorway'},(255,200,135,185),4)]
for cls,col,wd in STY:
    for r in rows:
        if r['class'] in cls and '_g' in r:
            cs=[(px(*c)[0]/W*TW*S, px(*c)[1]/H*TH*S) for c in r['_g'].coords]
            if len(cs)>1: dr.line(cs,fill=col,width=wd*S//1 if wd>1 else S, joint='curve')
ov=ov.resize((TW,TH),Image.LANCZOS); ov.save('dem/roads_bg.png'); print('overlay done')
