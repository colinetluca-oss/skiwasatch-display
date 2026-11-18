import numpy as np, math, json, base64, io
from PIL import Image, ImageFilter
C=np.load('crop.npy'); M=json.load(open('meta.json')); h,w=C.shape; mpp=14.49
def px(lon,lat):
    n=2**M['z']*256; x=(lon+180)/360*n; r=math.radians(lat); y=(1-math.log(math.tan(r)+1/math.cos(r))/math.pi)/2*n
    return x-M['x0'], y-M['y0']
def blur(a,r):
    k=int(3*r)+1; x=np.arange(-k,k+1); g=np.exp(-x**2/(2*r*r)); g/=g.sum()
    a=a.astype(np.float32)
    p=np.pad(a,((0,0),(k,k)),mode='edge'); a=sum(g[i]*p[:,i:i+a.shape[1]] for i in range(len(g)))
    p=np.pad(a,((k,k),(0,0)),mode='edge'); a=sum(g[i]*p[i:i+a.shape[0],:] for i in range(len(g)))
    return a.astype(np.float32)
# ---------- shading ----------
gy,gx=np.gradient(C,mpp)
def lam(az,alt):
    az=math.radians(az); alt=math.radians(alt)
    lx,ly,lz=math.sin(az)*math.cos(alt), -math.cos(az)*math.cos(alt), math.sin(alt)  # x east, y down(south)
    n=np.sqrt(gx**2+gy**2+1); return np.clip((-gx*lx - gy*ly + lz)/n,0,1)
shade=0.62*lam(245,32)+0.22*lam(315,45)+0.16*lam(180,60)
slope=np.degrees(np.arctan(np.sqrt(gx**2+gy**2)))
ridge=C-blur(C,6)            # local relief: + on ridges, - in gullies
rng=np.random.default_rng(7)
noise=blur(rng.random(C.shape).astype(np.float32),2.6); noise=(noise-noise.mean())/noise.std()
def ss(a,b,x): t=np.clip((x-a)/(b-a),0,1); return t*t*(3-2*t)
e=C
snow=ss(1650,2150,e)
north=np.clip(-(gy)/ (np.sqrt(gx**2+gy**2)+1e-3),-1,1)  # gy>0 means rising to south => north-facing? use aspect
trees=ss(1750,2000,e)*(1-ss(2650,2950,e))*np.clip(0.55+0.25*noise+0.15*np.clip(-ridge/25,-1,1),0,1)*(1-ss(32,42,slope))
rock=ss(36,48,slope)*ss(2000,2400,e)
valley=np.array([24,30,40],np.float32); foot=np.array([52,56,62],np.float32)
snowc=np.array([226,234,244],np.float32); treec=np.array([38,48,52],np.float32); rockc=np.array([92,96,104],np.float32)
base=valley[None,None,:]*(1-ss(1400,1650,e))[...,None]+foot[None,None,:]*ss(1400,1650,e)[...,None]
col=base*(1-snow)[...,None]+snowc*snow[...,None]
col=col*(1-trees*0.6)[...,None]+treec*(trees*0.6)[...,None]
col=col*(1-rock*0.6)[...,None]+rockc*(rock*0.6)[...,None]
light=0.22+0.95*shade+np.clip(ridge/60,-0.15,0.15)
shadowtint=np.array([0.80,0.88,1.12],np.float32)  # blue shadows
lit=col*light[...,None]
lit=lit*(shadowtint*(1-np.clip(shade,0,1))[...,None]+np.clip(shade,0,1)[...,None])
# subtle city lights in the valley floor
img=Image.fromarray(np.clip(lit,0,255).astype(np.uint8))
img=img.filter(ImageFilter.UnsharpMask(1.5,60,2))
TW=4096; TH=round(h*TW/w); img=img.resize((TW,TH),Image.LANCZOS)
bg=Image.open('roads_bg.png').convert('RGBA').resize((TW,TH)); img=Image.alpha_composite(img.convert('RGBA'),bg).convert('RGB')
buf=io.BytesIO(); img.save(buf,'JPEG',quality=78,optimize=True); tex=base64.b64encode(buf.getvalue()).decode()
img.save('tex_preview.jpg',quality=82)
# ---------- mesh heights ----------
GW=720; GH=round(h*GW/w)
small=np.asarray(Image.fromarray(C.astype(np.float32)).resize((GW,GH),Image.BILINEAR),np.float32)
hm=np.round(small).astype('<u2'); hb=base64.b64encode(hm.tobytes()).decode()
# ---------- roads ----------
SEGS = {
  'foothill':[[-111.820,40.737],[-111.823,40.728],[-111.812,40.712],[-111.808,40.706]],
  'i215':[[-111.808,40.706],[-111.805,40.690],[-111.807,40.665],[-111.808,40.640],[-111.797,40.628],[-111.789,40.619]],
  'wasatch':[[-111.789,40.619],[-111.795,40.600],[-111.800,40.582],[-111.796,40.572]],
  'bccLow':[[-111.789,40.619],[-111.760,40.622],[-111.730,40.626],[-111.700,40.632],[-111.665,40.637],[-111.640,40.630],[-111.612,40.624],[-111.592,40.620]],
  'bccUp':[[-111.592,40.620],[-111.587,40.610],[-111.583,40.598]],
  'lccLow':[[-111.796,40.572],[-111.770,40.571],[-111.745,40.573],[-111.715,40.576],[-111.685,40.578],[-111.657,40.581]],
  'lccUp':[[-111.657,40.581],[-111.648,40.585],[-111.638,40.588]],
  'i80':[[-111.808,40.706],[-111.790,40.709],[-111.775,40.712],[-111.745,40.722],[-111.715,40.733],[-111.680,40.742],[-111.640,40.748],[-111.600,40.748],[-111.570,40.738],[-111.545,40.722]],
  'sr224':[[-111.545,40.722],[-111.535,40.700],[-111.522,40.678],[-111.508,40.651]]}
SNAP={'bccLow':(1,-1),'lccLow':(1,-1),'i80':(2,-3)}  # snap interior points to canyon floor
Cb=blur(C,2)
def samp(a,x,y):
    x=min(max(x,0),w-1); y=min(max(y,0),h-1); return a[int(y),int(x)]
roads=json.load(open('../routes.json'))
def uv(lon,lat): x,y=px(lon,lat); return [round(x/w,5),round(y/h,5)]
places={'alta':uv(-111.638,40.588),'snowbird':uv(-111.657,40.581),'solitude':uv(-111.592,40.620),'brighton':uv(-111.583,40.598),'park':uv(-111.508,40.651),'home':uv(-111.820,40.737)}
peaks=[['Mt Olympus',(-111.7714,40.6563)],['Twin Peaks',(-111.7219,40.5938)],['Lone Peak',(-111.7563,40.5268)],['Gobblers Knob',(-111.6831,40.6669)],['Mt Superior',(-111.6655,40.5965)],['Clayton Peak',(-111.5543,40.5865)]]
pk=[]
for n,(lo,la) in peaks:
    x,y=px(lo,la); xi,yi=int(x),int(y)
    win=C[max(yi-25,0):yi+26,max(xi-25,0):xi+26]; j=np.unravel_index(win.argmax(),win.shape)
    X=max(xi-25,0)+j[1]; Y=max(yi-25,0)+j[0]
    pk.append({'n':n,'uv':[round(X/w,5),round(Y/h,5)],'ft':int(round(C[Y,X]*3.28084,-1))})
json.dump({'tex':tex,'hm':hb,'gw':GW,'gh':GH,'wm':w*mpp,'hm_m':h*mpp,'roads':roads,'places':places,'peaks':pk},open('terrain.json','w'))
print(GW,GH,len(tex)//1024,'KB tex',len(hb)//1024,'KB hm', pk)
