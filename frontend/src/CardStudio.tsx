import { useMemo, useState } from "react";
import { ArrowDownUp, Download, ImagePlus, Printer, RotateCcw, Save, SlidersHorizontal } from "lucide-react";

type Req = <T>(path:string, options?:RequestInit)=>Promise<T>;
type Side = "front"|"back";
type Photo = {url:string; name:string};
const PRESETS = {
  pvc: {label:"PVC ID card · CR80", w:1011, h:638, mm:"85.6 × 54 mm"},
  passport: {label:"Passport photo · 35 × 45 mm", w:413, h:531, mm:"35 × 45 mm"},
  square: {label:"Square photo · 2 × 2 inch", w:600, h:600, mm:"50.8 × 50.8 mm"},
  custom: {label:"Custom size", w:1011, h:638, mm:"Custom"}
} as const;
type Preset = keyof typeof PRESETS;
export default function CardStudio({request,onSave}:{request:Req;onSave:(title:string,data:Record<string,unknown>)=>Promise<void>}){
 const [mode,setMode]=useState<"card"|"passport">("card");
 const [preset,setPreset]=useState<Preset>("pvc");
 const [front,setFront]=useState<Photo|null>(null),[back,setBack]=useState<Photo|null>(null);
 const [active,setActive]=useState<Side>("front");
 const [zoom,setZoom]=useState(1),[x,setX]=useState(50),[y,setY]=useState(50);
 const [passport,setPassport]=useState<Photo|null>(null);
 const [busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const [customW,setCustomW]=useState(1011),[customH,setCustomH]=useState(638);
 const current=active==="front"?front:back;
 const dimensions=mode==="passport"?PRESETS[preset==="passport"?"passport":preset==="square"?"square":"passport"]:{...PRESETS[preset],w:preset==="custom"?customW:PRESETS[preset].w,h:preset==="custom"?customH:PRESETS[preset].h};
 const preview=useMemo(()=>current?.url||"",[current]);
 function setSidePhoto(side:Side,p:Photo|null){side==="front"?setFront(p):setBack(p);}
 function readFile(file:File,side:Side){if(!file.type.startsWith("image/")){setMessage("Please choose a valid image file.");return;}const url=URL.createObjectURL(file);setSidePhoto(side,{url,name:file.name});setActive(side);setZoom(1);setX(50);setY(50);setMessage("");}
 function choosePassport(file:File){if(!file.type.startsWith("image/")){setMessage("Please choose a valid image file.");return;}setPassport({url:URL.createObjectURL(file),name:file.name});}
 function swap(){const f=front;setFront(back);setBack(f);setMessage("Front and back images swapped.");}
 async function renderImage(photo:Photo,w:number,h:number):Promise<Blob>{
  const img=new Image();img.src=photo.url;await new Promise<void>((resolve,reject)=>{img.onload=()=>resolve();img.onerror=()=>reject(new Error("Could not read image"));});
  const canvas=document.createElement("canvas");canvas.width=w;canvas.height=h;const ctx=canvas.getContext("2d");if(!ctx)throw new Error("Canvas is unavailable");
  const scale=Math.max(w/img.width,h/img.height)*zoom;const dw=img.width*scale,dh=img.height*scale;const overflowX=dw-w,overflowY=dh-h;const sx=-(overflowX*x/100),sy=-(overflowY*y/100);
  ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality="high";ctx.fillStyle="#fff";ctx.fillRect(0,0,w,h);ctx.drawImage(img,sx,sy,dw,dh);
  return await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error("Image export failed")),"image/png"));
 }
 async function download(photo:Photo|null,w:number,h:number,name:string){if(!photo){setMessage("Upload an image first.");return;}try{const blob=await renderImage(photo,w,h);const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);setMessage("High-resolution PNG exported.");}catch(e){setMessage(e instanceof Error?e.message:"Export failed");}}
 async function saveCard(){if(!front&&!back){setMessage("Upload at least one card side.");return;}setBusy(true);try{const data:Record<string,unknown>={preset,width:dimensions.w,height:dimensions.h,front_name:front?.name||"",back_name:back?.name||"",front_preview:front?.url||"",back_preview:back?.url||"",front_crop:{zoom,x,y},back_crop:{zoom,x,y}};await onSave("ID / PVC card design",data);setMessage("Card design details saved.");}catch(e){setMessage(e instanceof Error?e.message:"Save failed");}finally{setBusy(false);}}
 return <div className="card-studio">
  <div className="studio-toolbar"><div><h3>Advanced card & photo studio</h3><p>Remove the extra name / ID overlays. Your uploaded front and back artwork stays clean.</p></div><div className="studio-mode"><button className={mode==="card"?"active":""} onClick={()=>setMode("card")}>PVC card</button><button className={mode==="passport"?"active":""} onClick={()=>{setMode("passport");setPreset("passport");}}>Passport photo</button></div></div>
  {mode==="card"?<>
   <div className="studio-controls"><label>Output size<select value={preset} onChange={e=>setPreset(e.target.value as Preset)}>{Object.entries(PRESETS).filter(([k])=>k!=="passport"&&k!=="square").map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select></label>{preset==="custom"&&<><label>Width (px)<input type="number" min="100" max="5000" value={customW} onChange={e=>setCustomW(Math.max(100,Number(e.target.value)))}/></label><label>Height (px)<input type="number" min="100" max="5000" value={customH} onChange={e=>setCustomH(Math.max(100,Number(e.target.value)))}/></label></>}<div className="studio-size-note">Export: {dimensions.w} × {dimensions.h}px · {dimensions.mm} · PNG</div></div>
   <div className="card-studio-grid"><div className="studio-edit">
    <div className="side-switch"><button className={active==="front"?"active":""} onClick={()=>setActive("front")}>Front side</button><button className={active==="back"?"active":""} onClick={()=>setActive("back")}>Back side</button><button onClick={swap} title="Swap front and back"><ArrowDownUp size={15}/> Swap</button></div>
    <label className="studio-upload"><ImagePlus size={19}/><span>{current?"Replace "+active+" image":"Upload "+active+" image"}</span><input type="file" accept="image/*" onChange={e=>{const f=e.target.files?.[0];if(f)readFile(f,active);e.currentTarget.value="";}}/></label>
    {current&&<><div className="crop-controls"><div><SlidersHorizontal size={15}/> Crop & position</div><label>Zoom <input type="range" min="1" max="2.5" step=".01" value={zoom} onChange={e=>setZoom(Number(e.target.value))}/></label><label>Horizontal <input type="range" min="0" max="100" value={x} onChange={e=>setX(Number(e.target.value))}/></label><label>Vertical <input type="range" min="0" max="100" value={y} onChange={e=>setY(Number(e.target.value))}/></label><button className="secondary" onClick={()=>{setZoom(1);setX(50);setY(50);}}><RotateCcw size={14}/> Reset crop</button></div>
    <div className="studio-preview" style={{aspectRatio:dimensions.w+"/"+dimensions.h}}><img src={preview} alt={active+" preview"} style={{objectFit:"cover",objectPosition:x+"% "+y+"%",transform:"scale("+zoom+")"}}/></div>
    <button className="primary" onClick={()=>void download(current,dimensions.w,dimensions.h,"sujaai-"+active+"-"+dimensions.w+"x"+dimensions.h+".png")}><Download size={16}/> Export {active} PNG</button></>}
   </div><div className="studio-both"><h4>Front & back preview</h4>{(["front","back"] as Side[]).map(side=>{const p=side==="front"?front:back;return <div className="mini-side" key={side}><span>{side.toUpperCase()}</span>{p?<img src={p.url} alt={side}/>:<div className="mini-empty">Upload {side} image</div>}</div>;})}<button className="primary" disabled={busy||(!front&&!back)} onClick={()=>void saveCard()}><Save size={16}/>{busy?"Saving…":"Save card design"}</button><button className="secondary" onClick={()=>window.print()}><Printer size={16}/> Print front & back</button><p className="studio-help">Use a 300 DPI printer setting where available. Check actual card dimensions and duplex flip direction with a test print before printing multiple cards.</p></div></div>
  </>:<div className="passport-studio"><div className="studio-edit"><h4>Passport-size photo crop</h4><p>Upload a clear photo, position the face inside the frame, then export a standard 35 × 45 mm image.</p><label className="studio-upload"><ImagePlus size={19}/> Upload portrait<input type="file" accept="image/*" onChange={e=>{const f=e.target.files?.[0];if(f)choosePassport(f);e.currentTarget.value="";}}/></label>{passport&&<><div className="passport-preview"><img src={passport.url} alt="Passport photo preview" style={{objectPosition:x+"% "+y+"%",transform:"scale("+zoom+")"}}/></div><label>Zoom <input type="range" min="1" max="2.5" step=".01" value={zoom} onChange={e=>setZoom(Number(e.target.value))}/></label><label>Horizontal <input type="range" min="0" max="100" value={x} onChange={e=>setX(Number(e.target.value))}/></label><label>Vertical <input type="range" min="0" max="100" value={y} onChange={e=>setY(Number(e.target.value))}/></label><button className="primary" onClick={()=>void download(passport,413,531,"passport-photo-35x45mm.png")}><Download size={16}/> Export 35 × 45 mm PNG</button><button className="secondary" onClick={()=>void download(passport,600,600,"photo-2x2-inch.png")}><Download size={16}/> Export 2 × 2 inch PNG</button></>}</div><div className="passport-info"><h4>Photo output sizes</h4><p><b>35 × 45 mm</b><br/>413 × 531 pixels at 300 DPI</p><p><b>2 × 2 inch</b><br/>600 × 600 pixels at 300 DPI</p><p className="studio-help">Official photo rules vary by application. Check the relevant authority's background, face-position and file-size requirements before submitting.</p></div></div>}
  {message&&<div className="studio-message" role="status">{message}<button onClick={()=>setMessage("")}>Dismiss</button></div>}
 </div>;
}
