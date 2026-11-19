import {useEffect,useState} from "react";
import {Save,Printer,Download,Archive,Users,Wallet,ReceiptText,FileText,CreditCard} from "lucide-react";
import CardStudio from "./CardStudio";
import ResumeStudio from "./ResumeStudio";
type Item={id:number;type:string;title:string;data:Record<string,any>};
type Req=<T>(path:string,options?:RequestInit)=>Promise<T>;
const root=String(import.meta.env.VITE_API_BASE_URL||"/api").replace(/\/+$/,"").replace(/\/api$/,"");
const img=(p:string)=>p.startsWith("http")?p:root+p;
export default function BusinessSuite({request}:{request:Req}){
 const [tab,setTab]=useState("customer"),[items,setItems]=useState<Item[]>([]),[msg,setMsg]=useState(""),[err,setErr]=useState("");
 const [form,setForm]=useState<Record<string,string>>({}),[photo,setPhoto]=useState(""),[file,setFile]=useState<File|null>(null);
 const [accent,setAccent]=useState("#087d59");
 async function load(){try{setItems(await request<Item[]>("workspace/records"));}catch(e){setErr(e instanceof Error?e.message:"Load failed");}}
 useEffect(()=>{void load();},[]);
 function val(k:string){return form[k]||""}
 function set(k:string,v:string){setForm(p=>({...p,[k]:v}))}
 async function save(type:string,title:string,data:any){try{await request("workspace/records",{method:"POST",body:JSON.stringify({type,title,data})});setMsg("Saved: "+title);setErr("");setForm({});await load();}catch(e){setErr(e instanceof Error?e.message:"Save failed");}}
 async function upload(f:File,which:string){const d=new FormData();d.append("file",f);try{const r=await request<{url:string}>("workspace/media",{method:"POST",body:d});if(which==="photo")setPhoto(r.url);setMsg("Image uploaded");}catch(e){setErr(e instanceof Error?e.message:"Upload failed");}}
 async function backup(){try{const data=await request<any>("workspace/backup");const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=u;a.download="sujaai-backup.json";a.click();URL.revokeObjectURL(u);}catch(e){setErr(e instanceof Error?e.message:"Backup failed");}}
 async function restore(){if(!file)return;try{const data=JSON.parse(await file.text());const r=await request<{restored:number}>("workspace/restore",{method:"POST",body:JSON.stringify(data)});setMsg(String(r.restored)+" records restored");await load();}catch(e){setErr(e instanceof Error?e.message:"Restore failed");}}
 const list=items.filter(x=>x.type===tab);
 const field=(label:string,key:string,type="text")=><label className="suite-label">{label}<input type={type} value={val(key)} onChange={e=>set(key,e.target.value)}/></label>;
 const uploadField=(label:string,which:string)=><label className="suite-label">{label}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f,which)}}/></label>;
 const tabs=[["customer","Customers",<Users/>],["chit_payment","Chit & payments",<Wallet/>],["receipt","Receipts & bills",<ReceiptText/>],["resume","Resume designer",<FileText/>],["id_card","ID / PVC cards",<CreditCard/>],["backup","Backup",<Archive/>]] as const;
 return <section className="panel suite-panel"><div className="panel-head"><div><h3>Business tools studio</h3><p>Customer records, collections, resumes, cards and backups</p></div><button className="secondary" onClick={()=>void load()}>Refresh</button></div>
 <div className="suite-tabs">{tabs.map(t=><button key={t[0]} className={tab===t[0]?"suite-tab active":"suite-tab"} onClick={()=>{setTab(t[0]);setForm({});}}>{t[2]}{t[1]}</button>)}</div>
 {msg&&<div className="success">{msg}<button onClick={()=>setMsg("")}>Dismiss</button></div>}{err&&<div className="error">{err}<button onClick={()=>setErr("")}>Dismiss</button></div>}
 {tab==="customer"&&<div className="suite-grid"><div className="suite-form"><h3>Customer entry</h3>{field("Customer name","name")}{field("Mobile number","phone")}{field("Address","address")}<button className="primary" onClick={()=>void save("customer",val("name"),form)} disabled={!val("name")}> <Save size={16}/> Save customer</button></div><Records items={list}/></div>}
 {tab==="chit_payment"&&<div className="suite-grid"><div className="suite-form"><h3>Chit collection entry</h3>{field("Chit group","group")}{field("Member name / ID","member")}{field("Amount (INR)","amount","number")}{field("Collection date","date","date")}{field("Notes","notes")}<button className="primary" onClick={()=>void save("chit_payment",val("group")+" - "+val("member"),{...form,amount:Number(val("amount"))})} disabled={!val("group")||!val("member")||Number(val("amount"))<=0}><Save size={16}/> Save payment</button></div><Records items={list} money/></div>}
 {tab==="receipt"&&<div className="suite-grid"><div className="suite-form"><h3>Receipt / bill entry</h3>{field("Customer","customer")}{field("Amount (INR)","amount","number")}{field("Purpose","purpose")}{field("Date","date","date")}<button className="primary" onClick={()=>void save("receipt","Receipt - "+val("customer"),{...form,amount:Number(val("amount"))})} disabled={!val("customer")||Number(val("amount"))<=0}><Save size={16}/> Save receipt</button><button className="secondary" onClick={()=>window.print()}><Printer size={16}/> Print records</button></div><Records items={list} money/></div>}
 {tab==="resume"&&<div className="resume-studio-shell"><ResumeStudio onSave={data=>void save("resume","Resume - "+String(data.html||"").replace(/<[^>]+>/g," ").trim().slice(0,55),data)}/><Records items={list}/></div>}
 {tab==="id_card"&&<CardStudio request={request} onSave={(title,data)=>save("id_card",title,data)}/>}\n {tab==="backup"&&<div className="suite-form backup-panel"><h3>Data backup & restore</h3><p>Download your workspace records. Restore appends records and leaves existing entries unchanged.</p><button className="primary" onClick={()=>void backup()}><Download size={16}/> Download JSON backup</button><label className="suite-label">Select backup file<input type="file" accept=".json,application/json" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><button className="secondary" disabled={!file} onClick={()=>void restore()}><Archive size={16}/> Restore backup</button><p className="hint">Backup contains workspace records, not account secrets or WhatsApp credentials. Store copies securely.</p></div>}
 </section>;
}
function Records({items,money=false}:{items:Item[];money?:boolean}){return <div className="suite-records"><h3>Saved records ({items.length})</h3>{items.length?items.slice(0,40).map(x=><div className="suite-record" key={x.id}><b>{x.title}</b><strong>{money&&x.data.amount?"₹"+Number(x.data.amount).toLocaleString("en-IN"):"Saved"}</strong></div>):<p className="muted">No saved records yet.</p>}</div>}
