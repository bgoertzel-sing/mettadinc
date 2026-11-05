
import re,html,os,subprocess,json,sys,time
root='1QNkx4elmZw0qUf7oQADHkZXr28ERsybW'
out=os.path.expanduser('~/scratch/mettadinc-e0/raw')
manifest=[]
def get(url,dest):
    r=subprocess.run(['curl','-sSL','--retry','3','-o',dest,'-w','%{http_code}',url],capture_output=True,text=True)
    return r.stdout
def listf(fid):
    s=subprocess.run(['curl','-sL','https://drive.google.com/embeddedfolderview?id='+fid],capture_output=True,text=True).stdout
    return [(m.group(1),html.unescape(m.group(2)),html.unescape(m.group(3))) for m in re.finditer(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?flip-entry-title">([^<]*)<',s,re.S)]
def walk(fid,path):
    os.makedirs(os.path.join(out,path),exist_ok=True)
    for id_,url,name in listf(fid):
        p=os.path.join(path,name)
        if '/folders/' in url:
            manifest.append({'kind':'folder','id':id_,'path':p,'url':url}); walk(id_,p)
        elif 'docs.google.com/document' in url:
            for fmt in ['md','txt','pdf']:
                code=get(f'https://docs.google.com/document/d/{id_}/export?format={fmt}',os.path.join(out,p+'.'+fmt))
                manifest.append({'kind':'gdoc','id':id_,'path':p+'.'+fmt,'url':url,'http':code})
        elif 'docs.google.com' in url:
            manifest.append({'kind':'other-gapp','id':id_,'path':p,'url':url})
        else:
            code=get(f'https://drive.usercontent.google.com/download?id={id_}&export=download&confirm=t',os.path.join(out,p))
            manifest.append({'kind':'file','id':id_,'path':p,'url':url,'http':code})
walk(root,'')
json.dump(manifest,open(os.path.expanduser('~/scratch/mettadinc-e0/manifest.json'),'w'),indent=1)
for m in manifest: print(m['kind'],m.get('http',''),m['path'])
