import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import ResumeDesigner from "./ResumeDesigner";
import PvcDesigner from "./PvcDesigner";

type Group={id:number;group_code:string;name:string;chit_type:string;default_amount:string;start_date:string;status:string;description?:string};
type Member={id:number;member_code:string;group_id:number;name:string;mobile:string;address:string;joining_date:string;status:string;notes?:string};
type Payment={id:number;payment_ref:string;member_id:number;amount:string;paid_at:string;frequency:string;notes?:string;recorded_by:string};
type Summary={total_collection:string;payment_count:number;group_totals:{group_name:string;collection:string}[]};
type GroupDetail={group:Group;total_members:number;lifetime_collection:string;payment_count:number;current_week_collection:string;current_week_payment_count:number;week_start:string;weekly_totals:PeriodRow[]};
type MemberDetails={member:Member;payment_count:number;lifetime_paid:string;current_week_paid:string;current_week_payment_count:number;paid_weeks:number;week_start:string;weekly_totals:PeriodRow[];payments:Payment[]};
type User={id:number;email:string;role:string;is_active:boolean;created_at:string};
type PeriodRow={period:string;total:string;entries:number};
type AuditRow={id:number;actor:string;action:string;entity_type:string;entity_id:string;details:string;created_at:string};
type Page="dashboard"|"groups"|"members"|"payments"|"reports"|"backup"|"resume"|"pvc"|"users";
const API = ((import.meta as any).env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const IS_PRODUCTION = Boolean((import.meta as any).env.PROD);

async function readApiResponse(response: Response): Promise<any> {
 const raw = await response.text();
 if (!raw) return {};
 const contentType = response.headers.get("content-type") || "";
 if (contentType.includes("application/json")) {
  try { return JSON.parse(raw); }
  catch { throw new Error(`Backend returned invalid JSON (HTTP ${response.status}).`); }
 }
 const preview = raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 160);
 throw new Error(`Backend returned a non-JSON page (HTTP ${response.status}). Check the frontend VITE_API_BASE_URL points to the deployed SUJAAI backend origin, without /api. Response: ${preview || "empty response"}`);
}

function connectionErrorMessage(error:unknown):string{
 const message=error instanceof Error?error.message:String(error||"Network request failed");
 if(typeof navigator!=="undefined"&&!navigator.onLine){
  return "Your device appears to be offline. Reconnect to the internet, then select Refresh to reload SUJAAI data.";
 }
 if(error instanceof TypeError||/failed to fetch|networkerror|load failed/i.test(message)){
  return "SUJAAI could not reach the backend. Check your internet connection and confirm the Render service is Live. Backend URL: https://suja-bxf5.onrender.com. If the browser console explicitly reports a CORS policy error, verify CORS_ORIGINS includes https://suja-in.vercel.app.";
 }
 return message;
}

function ensureApiConfigured(): void {
 if (!IS_PRODUCTION) return;
 if (!API) {
  throw new Error("Backend URL is not configured. In the FRONTEND Vercel project, set VITE_API_BASE_URL to your backend origin (https://your-backend.vercel.app), then redeploy the frontend.");
 }
 let parsed: URL;
 try {
  parsed = new URL(API);
 } catch {
  throw new Error("VITE_API_BASE_URL must be a complete backend URL starting with https://. Do not use a relative path such as /api.");
 }
 if (parsed.protocol !== "https:") {
  throw new Error("Production VITE_API_BASE_URL must use https://.");
 }
 if (parsed.origin === window.location.origin) {
  throw new Error("VITE_API_BASE_URL points to this frontend website, not the backend. Set it to the separate FastAPI backend Vercel domain.");
 }
 if (parsed.pathname !== "/" || parsed.search || parsed.hash) {
  throw new Error("VITE_API_BASE_URL must contain only the backend origin, without /api, extra paths, query strings or fragments.");
 }
}
function localDateKey(value:Date|string):string{
 const date=value instanceof Date?value:new Date(value);
 if(Number.isNaN(date.getTime()))return "";
 return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
}
const today=localDateKey(new Date());
const localDateTimeNow=()=>{const d=new Date();d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16);};
const toLocalDateTimeInput=(value:Date|string)=>{const d=value instanceof Date?new Date(value):new Date(value);if(Number.isNaN(d.getTime()))return localDateTimeNow();d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16);};
const money=(v:string|number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(Number(v||0));

export default function App(){
 const [token,setToken]=useState(sessionStorage.getItem("sujaai_token")||"");
 const [role,setRole]=useState("owner");
 const [email,setEmail]=useState(""); const [password,setPassword]=useState("");
 const [page,setPage]=useState<Page>("dashboard"); const [dark,setDark]=useState(localStorage.getItem("sujaai_theme")==="dark");
 const [groups,setGroups]=useState<Group[]>([]); const [members,setMembers]=useState<Member[]>([]);
 const [payments,setPayments]=useState<Payment[]>([]); const [summary,setSummary]=useState<Summary|null>(null);
 const [users,setUsers]=useState<User[]>([]); const [auditRows,setAuditRows]=useState<AuditRow[]>([]); const [periodRows,setPeriodRows]=useState<PeriodRow[]>([]); const [reportSummary,setReportSummary]=useState<Summary|null>(null);
 const [notice,setNotice]=useState(""); const [busy,setBusy]=useState(false);
 const [search,setSearch]=useState(""); const [groupFilter,setGroupFilter]=useState<number| "">(""); const [memberCreateGroup,setMemberCreateGroup]=useState<number| "">("");
 const [selectedGroupId,setSelectedGroupId]=useState<number|null>(null); const [selectedMemberId,setSelectedMemberId]=useState<number|null>(null);
 const [groupDetails,setGroupDetails]=useState<GroupDetail|null>(null); const [memberDetails,setMemberDetails]=useState<MemberDetails|null>(null);
 const [showAddGroup,setShowAddGroup]=useState(false); const [showAddMember,setShowAddMember]=useState(false); const [showAddPayment,setShowAddPayment]=useState(false); const [ownerPassword,setOwnerPassword]=useState("");
 const [period,setPeriod]=useState("monthly"); const [reportStart,setReportStart]=useState(""); const [reportEnd,setReportEnd]=useState("");
 const [groupForm,setGroupForm]=useState({group_code:"",name:"",chit_type:"monthly",default_amount:"",start_date:today,description:""});
 const [memberForm,setMemberForm]=useState({member_code:"",name:"",mobile:"",address:"",joining_date:today,notes:""});
 const [paymentForm,setPaymentForm]=useState({member_id:"",amount:"",paid_at:localDateTimeNow(),notes:""});
 const [editing,setEditing]=useState<Payment|null>(null);
 const [editingGroup,setEditingGroup]=useState<Group|null>(null);const [groupEditForm,setGroupEditForm]=useState({name:"",chit_type:"monthly",default_amount:"",start_date:today,description:"",status:"active"});
 const [editingMember,setEditingMember]=useState<Member|null>(null);const [memberEditForm,setMemberEditForm]=useState({name:"",mobile:"",address:"",joining_date:today,notes:"",status:"active"});
 const [editForm,setEditForm]=useState({amount:"",paid_at:"",notes:""});
 const [newUser,setNewUser]=useState({email:"",password:"",role:"staff"});

 const request=useCallback(async <T = unknown,>(path:string,init:RequestInit={}):Promise<T>=>{
  ensureApiConfigured();
  const method=(init.method||"GET").toUpperCase();
  const safeToRetry=method==="GET"||method==="HEAD";
  let response:Response|undefined;
  for(let attempt=0;attempt<(safeToRetry?3:1);attempt++){
   try{
    response=await fetch(API+path,{...init,headers:{"Content-Type":"application/json",...(token?{Authorization:`Bearer ${token}`}:{}),...init.headers}});
   }catch(error){
    if(safeToRetry&&attempt<2&&navigator.onLine!==false){
     await new Promise(resolve=>window.setTimeout(resolve,900*(attempt+1)));
     continue;
    }
    throw new Error(connectionErrorMessage(error));
   }
   if(safeToRetry&&[502,503,504].includes(response.status)&&attempt<2){
    if(response.body)await response.body.cancel().catch(()=>undefined);
    await new Promise(resolve=>window.setTimeout(resolve,900*(attempt+1)));
    continue;
   }
   break;
  }
  if(!response)throw new Error("Backend did not return a response. Check your internet connection and try again.");
  if(response.status===401){sessionStorage.removeItem("sujaai_token");setToken("");throw new Error("Session expired. Sign in again.");}
  const data=await readApiResponse(response);
  if(!response.ok){const detail=Array.isArray(data.detail)?data.detail.map((item:any)=>`${Array.isArray(item.loc)?item.loc.filter((part:any)=>part!=="body"&&part!=="query").join("."):"request"}: ${item.msg||"Invalid value"}`).join("; "):typeof data.detail==="string"?data.detail:`Request failed (HTTP ${response.status})`;throw new Error(detail||`Request failed (HTTP ${response.status})`);}
  return data as T;
 },[token]);

 const refresh=useCallback(async()=>{
  // Check/wake the API before fanning out dashboard requests; Render free instances can sleep.
  const health=await request<{status:string}>("/api/health");
  if(health.status!=="ok")throw new Error("The configured backend did not return a healthy SUJAAI API response.");
  const [g,m,p,s,me]=await Promise.all([
   request<Group[]>("/api/chit/groups"),request<Member[]>("/api/chit/members?limit=500"),
   request<Payment[]>("/api/chit/payments?limit=500"),request<Summary>("/api/chit/reports/summary"),request<{email:string;role:string}>("/api/auth/me")
  ]);
  setGroups(g);setMembers(m);setPayments(p);setSummary(s);setRole(me.role);setEmail(me.email);
  if(me.role==="owner"||me.role==="admin"){const u=await request<User[]>("/api/users");setUsers(u);}
 },[request]);

 const loadPeriod=useCallback(async()=>{
  const qs=new URLSearchParams({period});if(reportStart)qs.set("start",reportStart);if(reportEnd)qs.set("end",reportEnd);
  const dates=new URLSearchParams();if(reportStart)dates.set("start",reportStart);if(reportEnd)dates.set("end",reportEnd);
  const [rows,sums]=await Promise.all([request<PeriodRow[]>(`/api/chit/reports/periods?${qs.toString()}`),request<Summary>(`/api/chit/reports/summary?${dates.toString()}`)]);setPeriodRows(rows);setReportSummary(sums);
 },[request,period,reportStart,reportEnd]);

 useEffect(()=>{
  const onOffline=()=>setNotice("Internet connection lost. Reconnect, then use Refresh to reload your SUJAAI data.");
  const onOnline=()=>setNotice("Internet connection restored. Select Refresh to reconnect to the SUJAAI backend.");
  window.addEventListener("offline",onOffline);
  window.addEventListener("online",onOnline);
  return ()=>{window.removeEventListener("offline",onOffline);window.removeEventListener("online",onOnline);};
 },[]);
 useEffect(()=>{if(token){refresh().catch(e=>setNotice(connectionErrorMessage(e)));}},[token,refresh]);
 useEffect(()=>{if(token&&page==="reports")loadPeriod().catch(e=>setNotice(e.message));},[token,page,loadPeriod]);
 useEffect(()=>{if(token&&page==="backup"&&(role==="owner"||role==="admin"))request<AuditRow[]>("/api/audit?limit=50").then(setAuditRows).catch(e=>setNotice(e.message));},[token,page,role,request]);
 useEffect(()=>{if(token&&page==="groups"&&selectedGroupId!==null){request<GroupDetail>(`/api/chit/groups/${selectedGroupId}`).then(setGroupDetails).catch(e=>setNotice(e.message));}else{setGroupDetails(null);}},[token,page,selectedGroupId,request,groups,members,payments]);
 useEffect(()=>{if(token&&page==="groups"&&selectedMemberId!==null){request<MemberDetails>(`/api/chit/members/${selectedMemberId}/details`).then(setMemberDetails).catch(e=>setNotice(e.message));}else{setMemberDetails(null);}},[token,page,selectedMemberId,request,members,payments]);
 useEffect(()=>{localStorage.setItem("sujaai_theme",dark?"dark":"light");},[dark]);

 async function checkBackend(){setBusy(true);setNotice("");try{ensureApiConfigured();const res=await fetch(API+"/api/health",{headers:{Accept:"application/json"}});const data=await readApiResponse(res);if(!res.ok)throw new Error(`Backend health check failed (HTTP ${res.status}).`);if(data.status!=="ok")throw new Error("The configured URL did not return the SUJAAI API health response.");setNotice("Backend connected successfully. API health: OK.");}catch(e){const message=(e as Error).message||"Connection failed.";setNotice(connectionErrorMessage(e));}finally{setBusy(false);}}
 async function signIn(e:FormEvent){e.preventDefault();setBusy(true);setNotice("");try{ensureApiConfigured();const res=await fetch(API+"/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});const data=await readApiResponse(res);if(!res.ok)throw new Error(data.detail||`Sign in failed (HTTP ${res.status})`);if(!data.access_token)throw new Error("Backend login response did not contain an access token.");sessionStorage.setItem("sujaai_token",data.access_token);setToken(data.access_token);setPassword("");}catch(e){setNotice(connectionErrorMessage(e));}finally{setBusy(false);}}
 function logout(){sessionStorage.removeItem("sujaai_token");setToken("");setPage("dashboard");}

 async function createGroup(e:FormEvent){e.preventDefault();setBusy(true);try{await request("/api/chit/groups",{method:"POST",body:JSON.stringify({...groupForm,default_amount:Number(groupForm.default_amount)})});setGroupForm({group_code:"",name:"",chit_type:"monthly",default_amount:"",start_date:today,description:""});setShowAddGroup(false);await refresh();setNotice("Group created.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function createMember(e:FormEvent){e.preventDefault();if(!memberCreateGroup)return;setBusy(true);try{await request("/api/chit/members",{method:"POST",body:JSON.stringify({...memberForm,group_id:memberCreateGroup})});setMemberForm({member_code:"",name:"",mobile:"",address:"",joining_date:today,notes:""});setShowAddMember(false);await refresh();setNotice("Member added to this chit group.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function createPayment(e:FormEvent){e.preventDefault();const member=members.find(x=>x.id===Number(paymentForm.member_id));const group=groups.find(x=>x.id===member?.group_id);if(!member||!group)return;setBusy(true);try{await request<Payment>("/api/chit/payments",{method:"POST",body:JSON.stringify({member_id:member.id,amount:paymentForm.amount,paid_at:new Date(paymentForm.paid_at).toISOString(),frequency:group.chit_type,notes:paymentForm.notes})});setPaymentForm({member_id:String(member.id),amount:String(group.default_amount),paid_at:localDateTimeNow(),notes:""});setShowAddPayment(false);await refresh();setNotice("Payment saved successfully.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function saveCorrection(e:FormEvent){e.preventDefault();if(!editing)return;setBusy(true);try{const needsApproval=localDateKey(editing.paid_at)!==localDateKey(new Date())||localDateKey(editForm.paid_at)!==localDateKey(new Date());await request(`/api/chit/payments/${editing.id}`,{method:"PATCH",body:JSON.stringify({amount:Number(editForm.amount),paid_at:new Date(editForm.paid_at).toISOString(),notes:editForm.notes,...(needsApproval?{owner_password:ownerPassword}:{})})});setEditing(null);setOwnerPassword("");await refresh();setNotice("Payment updated. The before/after change is saved in the audit log.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function saveGroupEdit(e:FormEvent){e.preventDefault();if(!editingGroup)return;setBusy(true);try{await request(`/api/chit/groups/${editingGroup.id}`,{method:"PATCH",body:JSON.stringify({...groupEditForm,default_amount:Number(groupEditForm.default_amount)})});setEditingGroup(null);await refresh();setNotice("Group details updated.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function saveMemberEdit(e:FormEvent){e.preventDefault();if(!editingMember)return;setBusy(true);try{await request(`/api/chit/members/${editingMember.id}`,{method:"PATCH",body:JSON.stringify(memberEditForm)});setEditingMember(null);await refresh();setNotice("Member details updated.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function toggleGroup(g:Group){try{await request(`/api/chit/groups/${g.id}`,{method:"PATCH",body:JSON.stringify({status:g.status==="active"?"paused":"active"})});await refresh();}catch(e){setNotice((e as Error).message);}}
 async function toggleMember(m:Member){try{await request(`/api/chit/members/${m.id}`,{method:"PATCH",body:JSON.stringify({status:m.status==="active"?"inactive":"active"})});await refresh();}catch(e){setNotice((e as Error).message);}}
 async function createStaff(e:FormEvent){e.preventDefault();setBusy(true);try{await request("/api/users",{method:"POST",body:JSON.stringify(newUser)});setNewUser({email:"",password:"",role:"staff"});await refresh();setNotice("User account created.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 async function toggleUser(u:User){try{await request(`/api/users/${u.id}`,{method:"PATCH",body:JSON.stringify({is_active:!u.is_active})});await refresh();}catch(e){setNotice((e as Error).message);}}

 async function download(path:string,filename:string):Promise<boolean>{try{ensureApiConfigured();const res=await fetch(API+path,{headers:{Authorization:`Bearer ${token}`}});if(!res.ok){const d=await res.json().catch(()=>({}));throw new Error(d.detail||"Download failed");}const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=filename;a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);return true;}catch(e){setNotice(connectionErrorMessage(e));return false;}}
 async function importBackup(file?:File){if(!file)return;setBusy(true);try{const parsed=JSON.parse(await file.text());if(!window.confirm("Restore this backup into an empty chit database? Existing chit records will not be overwritten."))return;const result=await request<{restored:boolean}>("/api/backup/json/restore",{method:"POST",body:JSON.stringify(parsed)});await refresh();setNotice(result.restored?"Backup restored.":"Restore not completed.");}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}}
 const filteredMembers=useMemo(()=>members.filter(m=>(!groupFilter||m.group_id===groupFilter)&&[m.name,m.member_code,m.mobile].some(v=>v.toLowerCase().includes(search.toLowerCase()))),[members,groupFilter,search]);
 const filteredPayments=useMemo(()=>payments.filter(p=>(!groupFilter||members.find(m=>m.id===p.member_id)?.group_id===groupFilter)&&[p.payment_ref,p.recorded_by,members.find(m=>m.id===p.member_id)?.name||""].some(v=>v.toLowerCase().includes(search.toLowerCase()))),[payments,members,groupFilter,search]);
 const activeGroups=useMemo(()=>groups.filter(g=>g.status==="active"),[groups]);
 const activeMembers=useMemo(()=>members.filter(m=>m.status==="active"),[members]);
 const inactiveMembers=members.length-activeMembers.length;
 const selectedPaymentMember=members.find(m=>m.id===Number(paymentForm.member_id));
 const selectedPaymentGroup=groups.find(g=>g.id===selectedPaymentMember?.group_id);
 const recentPayments=useMemo(()=>[...payments].sort((a,b)=>new Date(b.paid_at).getTime()-new Date(a.paid_at).getTime()).slice(0,6),[payments]);
 const collectionTrend=useMemo(()=>Array.from({length:7},(_,index)=>{
  const date=new Date();date.setHours(0,0,0,0);date.setDate(date.getDate()-(6-index));
  const key=localDateKey(date);
  const total=payments.filter(p=>localDateKey(p.paid_at)===key).reduce((sum,p)=>sum+Number(p.amount||0),0);
  return {key,label:date.toLocaleDateString("en-IN",{weekday:"short"}),total};
 }),[payments]);
 const trendMax=Math.max(1,...collectionTrend.map(item=>item.total));
 const groupCollectionMax=Math.max(1,...(summary?.group_totals||[]).map(item=>Number(item.collection||0)));
 const todayKey=localDateKey(new Date());
 const todayPayments=payments.filter(p=>localDateKey(p.paid_at)===todayKey);
 const todayCollection=todayPayments.reduce((sum,p)=>sum+Number(p.amount||0),0);
 const loadedPaymentTotal=payments.reduce((sum,p)=>sum+Number(p.amount||0),0);
 const averageLoadedPayment=payments.length?loadedPaymentTotal/payments.length:0;

 if(!token)return <main className="login-shell">
 <section className="login-showcase" aria-label="SUJAAI workspace introduction">
  <div className="showcase-orb orb-one"></div><div className="showcase-orb orb-two"></div>
  <div className="showcase-content">
   <div className="showcase-brand"><div className="brand-mark">S</div><div><strong>SUJAAI</strong><small>Management Suite</small></div></div>
   <p className="eyebrow">A CLEARER WAY TO MANAGE</p>
   <h2>Every collection.<br/><span>One confident view.</span></h2>
   <p className="showcase-copy">A focused workspace for your chit groups, members, payments and reports. Keep daily operations organized in one secure place.</p>
   <div className="showcase-points"><span><b>01</b> Organized groups</span><span><b>02</b> Clear payment records</span><span><b>03</b> Reports and exports</span></div>
   <div className="showcase-footer"><span className="showcase-dot"></span> Your workspace, all in one place</div>
  </div>
 </section>
 <section className="login-card">
  <div className="login-card-head"><div className="brand-mark">S</div><div><p className="eyebrow">SECURE WORKSPACE</p><h1>Welcome back</h1></div></div>
  <p className="muted">Sign in to continue to your SUJAAI workspace.</p>
  <form className="stack" onSubmit={signIn}>
   <label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="username" placeholder="you@example.com" required/></label>
   <label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" placeholder="Enter your password" required/></label>
   <button disabled={busy}>{busy?"Signing in…":"Sign in to SUJAAI"} <span aria-hidden="true">→</span></button>
  </form>
  {notice&&<p className="notice error">{notice}</p>}
  <button type="button" className="secondary backend-test" onClick={checkBackend} disabled={busy}>Check backend connection</button>
  <p className="login-security"><span>✓</span> Protected sign-in · Role-based workspace access</p>
  <p className="tiny">Need access? Ask your system owner to create an account.</p>
 </section>
</main>;

 const nav: {id:Page;label:string;icon:string}[]=[{id:"dashboard",label:"Overview",icon:"▦"},{id:"groups",label:"Chit",icon:"▧"},{id:"reports",label:"Reports",icon:"▤"},...((role==="owner"||role==="admin")?[{id:"backup" as Page,label:"Backup & export",icon:"⇩"}]:[]),{id:"resume",label:"Resume designer",icon:"▣"},{id:"pvc",label:"PVC card designer",icon:"▣"},...((role==="owner"||role==="admin")?[{id:"users" as Page,label:"Team access",icon:"♧"}]:[])];
 return <div className={`app-shell ${dark?"dark":""}`}><aside className="sidebar"><div className="brand"><div className="brand-mark">S</div><div><strong>SUJAAI</strong><small>Management Suite</small></div></div><div className="nav-label">WORKSPACE</div>{nav.map(n=><button key={n.id} className={`nav-item ${page===n.id?"active":""}`} onClick={()=>{setPage(n.id);if(n.id==="groups"){setSelectedGroupId(null);setSelectedMemberId(null);setShowAddGroup(false);setShowAddMember(false);setShowAddPayment(false);}setSearch("");setGroupFilter("");setNotice("");}}><span className="nav-icon">{n.icon}</span><span>{n.label}</span></button>)}<div className="sidebar-bottom"><div className="avatar">{role.charAt(0).toUpperCase()}</div><div className="profile"><strong>{role.toUpperCase()}</strong><small>{email||"Signed-in user"}</small></div><button className="signout" onClick={logout} title="Sign out">↪</button></div></aside>
 <main className="main"><header className="topbar"><div><p className="eyebrow">SUJAAI / WORKSPACE</p><h1>{nav.find(n=>n.id===page)?.label}</h1></div><div className="top-actions"><button className="secondary" onClick={()=>setDark(v=>!v)}>{dark?"☀ Light":"◐ Dark"}</button><button className="secondary" onClick={()=>refresh().catch(e=>setNotice(e.message))}>↻ Refresh</button></div></header>
 {notice&&<div className="notice">{notice}<button onClick={()=>setNotice("")}>×</button></div>}
 {page==="dashboard"&&<>
 <section className="welcome-banner">
  <div className="welcome-copy"><p className="eyebrow">YOUR WORKSPACE</p><h2>Welcome back<span>, {email.split("@")[0] || "there"}.</span></h2><p>Your chit operations, collections and members — all in one place.</p><small>{new Date().toLocaleDateString("en-IN",{weekday:"long",day:"numeric",month:"long",year:"numeric"})}</small></div>
  <div className="welcome-side"><span className="welcome-orbit orbit-a"></span><span className="welcome-orbit orbit-b"></span><div className="welcome-side-content"><span className="welcome-pill"><i></i> WORKSPACE</span><strong>{activeGroups.length.toString().padStart(2,"0")}</strong><span>Active groups</span><small>Signed in as {role}</small></div></div>
 </section>
 <section className="stats dashboard-stats">
  <article className="stat-card"><span className="stat-icon green">₹</span><p>Total collection</p><strong>{money(summary?.total_collection||0)}</strong><small>All saved payment records</small></article>
  <article className="stat-card"><span className="stat-icon blue">▦</span><p>Active groups</p><strong>{activeGroups.length}</strong><small>{groups.length-activeGroups.length} paused or completed</small></article>
  <article className="stat-card"><span className="stat-icon violet">♙</span><p>Active members</p><strong>{activeMembers.length}</strong><small>{inactiveMembers} inactive members</small></article>
  <article className="stat-card"><span className="stat-icon amber">↗</span><p>Payment entries</p><strong>{summary?.payment_count||0}</strong><small>Recorded transactions</small></article>
 </section>
 <section className="dashboard-grid">
  <article className="panel trend-panel">
   <div className="panel-head"><div><h2>Collection activity</h2><p>Daily totals from the latest loaded payment records.</p></div><span className="panel-tag">LAST 7 DAYS</span></div>
   <div className="trend-total"><strong>{money(collectionTrend.reduce((sum,item)=>sum+item.total,0))}</strong><span>Collected in this view</span></div>
   <div className="trend-chart" role="img" aria-label="Daily collection totals for the last seven days">
    {collectionTrend.map(item=><div className="trend-column" key={item.key} title={`${item.label}: ${money(item.total)}`}><div className="trend-bar-track"><div className="trend-bar" style={{height:`${Math.max(item.total?7:2,(item.total/trendMax)*100)}%`}}></div></div><span className="trend-value">{item.total?money(item.total):"—"}</span><span className="trend-label">{item.label}</span></div>)}
   </div>
  </article>
  <article className="panel snapshot-panel">
   <div className="panel-head"><div><h2>Today at a glance</h2><p>Based on payments loaded in this workspace.</p></div><span className="snapshot-icon">◷</span></div>
   <div className="snapshot-total"><strong>{money(todayCollection)}</strong><span>{todayPayments.length} payment{todayPayments.length===1?"":"s"} today</span></div>
   <div className="snapshot-divider"></div>
   <div className="snapshot-row"><span><i className="snapshot-dot violet-dot"></i> Active groups</span><b>{activeGroups.length}</b></div>
   <div className="snapshot-row"><span><i className="snapshot-dot green-dot"></i> Active members</span><b>{activeMembers.length}</b></div>
   <div className="snapshot-row"><span><i className="snapshot-dot amber-dot"></i> Average payment*</span><b>{money(averageLoadedPayment)}</b></div>
   <small className="snapshot-foot">*Average is calculated from the loaded payment list.</small>
  </article>
 </section>
 <section className="panel collection-panel">
  <div className="panel-head"><div><h2>Collection by group</h2><p>Group totals returned by the reports service.</p></div><button className="secondary" onClick={()=>setPage("reports")}>Open reports →</button></div>
  {groups.length? <div className="collection-list">{groups.map(g=>{const total=Number(summary?.group_totals.find(x=>x.group_name===g.name)?.collection||0);return <div className="collection-item" key={g.id}><div className="collection-meta"><div><b>{g.name}</b><small>{g.group_code} · {g.chit_type} · {members.filter(m=>m.group_id===g.id).length} members</small></div><strong>{money(total)}</strong></div><div className="collection-track"><span style={{width:`${Math.max(total?2:0,(total/groupCollectionMax)*100)}%`}}></span></div></div>})}</div>:<p className="empty">Create a chit group to see collection summaries here.</p>}
 </section>
 <section className="dashboard-grid dashboard-bottom">
  <article className="panel recent-panel"><div className="panel-head"><div><h2>Recent payments</h2><p>Latest entries in the loaded payment list.</p></div><button className="secondary" onClick={()=>setPage("payments")}>View ledger →</button></div>
   {recentPayments.length?<div className="recent-list">{recentPayments.map(p=>{const member=members.find(m=>m.id===p.member_id);const group=groups.find(g=>g.id===member?.group_id);return <div className="recent-row" key={p.id}><div className="recent-avatar">{(member?.name||"M").slice(0,1).toUpperCase()}</div><div className="recent-person"><b>{member?.name||"Unknown member"}</b><small>{p.payment_ref} · {group?.name||"No group"}</small></div><div className="recent-amount"><b>{money(p.amount)}</b><small>{new Date(p.paid_at).toLocaleDateString("en-IN",{day:"2-digit",month:"short"})}</small></div></div>})}</div>:<p className="empty">No payments have been recorded yet.</p>}
  </article>
  <article className="panel quick-panel"><div className="panel-head"><div><h2>Quick actions</h2><p>Jump straight into common tasks.</p></div></div>
   <div className="dashboard-quick-grid">
    <button className="dashboard-action" onClick={()=>setPage("groups")}><span>＋</span><b>Create group</b><small>Set up a contribution plan</small></button>
    <button className="dashboard-action" onClick={()=>setPage("members")}><span>♙</span><b>Add member</b><small>Register a participant</small></button>
    <button className="dashboard-action" onClick={()=>setPage("payments")}><span>₹</span><b>Record payment</b><small>Save a collection entry</small></button>
    <button className="dashboard-action" onClick={()=>setPage("reports")}><span>▤</span><b>View reports</b><small>Review collection totals</small></button>
   </div>
  </article>
 </section>
</>}
 {page==="groups"&&<>
 {!selectedGroupId&&<><section className="page-intro"><div><p className="eyebrow">CHIT MANAGEMENT</p><h2>Your chit groups</h2><p>Open a group to manage members, payments and weekly collections.</p></div><button className="chit-add-button" onClick={()=>setShowAddGroup(v=>!v)} disabled={role!=="owner"&&role!=="admin"}><span>＋</span> Add group</button></section>
 <section className="mini-stats"><div><span>Total groups</span><b>{groups.length}</b></div><div><span>Total members</span><b>{members.length}</b></div><div><span>Total collection</span><b>{money(summary?.total_collection||0)}</b></div><div><span>Payments recorded</span><b>{summary?.payment_count||0}</b></div></section>
 {showAddGroup&&(role==="owner"||role==="admin")&&<section className="panel chit-form-panel"><div className="panel-head"><div><span className="section-kicker">NEW CHIT GROUP</span><h2>Create group</h2><p>Set the group contribution and collection frequency.</p></div><button type="button" className="secondary" onClick={()=>setShowAddGroup(false)}>Close</button></div><form className="form-grid" onSubmit={createGroup}><label>Group ID<input value={groupForm.group_code} onChange={e=>setGroupForm({...groupForm,group_code:e.target.value})} required/></label><label>Group name<input value={groupForm.name} onChange={e=>setGroupForm({...groupForm,name:e.target.value})} required/></label><label>Frequency<select value={groupForm.chit_type} onChange={e=>setGroupForm({...groupForm,chit_type:e.target.value})}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label><label>Contribution amount (₹)<input type="number" min="0.01" step="0.01" value={groupForm.default_amount} onChange={e=>setGroupForm({...groupForm,default_amount:e.target.value})} required/></label><label>Start date<input type="date" value={groupForm.start_date} onChange={e=>setGroupForm({...groupForm,start_date:e.target.value})} required/></label><label>Description<input value={groupForm.description} onChange={e=>setGroupForm({...groupForm,description:e.target.value})}/></label><button className="wide" disabled={busy}>＋ Create group</button></form></section>}
 <section className="chit-group-grid">{groups.map(g=>{const count=members.filter(m=>m.group_id===g.id).length;const total=summary?.group_totals.find(x=>x.group_name===g.name)?.collection||"0";return <button type="button" className="chit-group-card" key={g.id} onClick={()=>{setSelectedGroupId(g.id);setSelectedMemberId(null);setShowAddMember(false);setShowAddPayment(false);}}><div className="chit-group-card-top"><span className="chit-group-symbol">₹</span><span className={`status ${g.status}`}>{g.status}</span></div><small>{g.group_code}</small><strong>{g.name}</strong><span className="chit-group-meta">{g.chit_type} · {money(g.default_amount)} per contribution</span><div className="chit-group-card-stats"><span><b>{count}</b> Members</span><span><b>{money(total)}</b> Collected</span></div><span className="chit-open-link">Open group <b>→</b></span></button>})}{!groups.length&&<div className="panel empty">No chit groups yet. Use “Add group” to create your first group.</div>}</section></>}
 {selectedGroupId!==null&&!selectedMemberId&&(()=>{const g=groups.find(x=>x.id===selectedGroupId);if(!g)return <section className="panel"><button className="secondary" onClick={()=>setSelectedGroupId(null)}>← Back to groups</button><p className="empty">Group not found.</p></section>;const groupMembers=members.filter(m=>m.group_id===g.id);const total=groupDetails?.lifetime_collection??summary?.group_totals.find(x=>x.group_name===g.name)?.collection??"0";return <><section className="chit-breadcrumb"><button onClick={()=>setSelectedGroupId(null)}>Chit groups</button><span>/</span><b>{g.name}</b></section><section className="page-intro"><div><p className="eyebrow">{g.group_code} · {g.chit_type.toUpperCase()} CHIT</p><h2>{g.name}</h2><p>{g.description||"Manage members and collections for this chit group."}</p></div><div className="chit-detail-actions">{(role==="owner"||role==="admin")&&<button className="secondary" onClick={()=>{setEditingGroup(g);setGroupEditForm({name:g.name,chit_type:g.chit_type,default_amount:g.default_amount,start_date:g.start_date,description:g.description||"",status:g.status});}}>Edit group</button>}<button className="chit-add-button" onClick={()=>{setMemberCreateGroup(g.id);setShowAddMember(v=>!v);}}>＋ Add chit member</button></div></section><section className="mini-stats"><div><span>Total members</span><b>{groupDetails?.total_members??groupMembers.length}</b></div><div><span>Total collection</span><b>{money(total)}</b></div><div><span>This week collected</span><b>{money(groupDetails?.current_week_collection||0)}</b></div><div><span>Payments this week</span><b>{groupDetails?.current_week_payment_count??0}</b></div></section>
 {showAddMember&&<section className="panel chit-form-panel"><div className="panel-head"><div><span className="section-kicker">NEW MEMBER</span><h2>Add member to {g.name}</h2><p>Member will be assigned to this group automatically.</p></div><button type="button" className="secondary" onClick={()=>setShowAddMember(false)}>Close</button></div><form className="form-grid" onSubmit={createMember}><label>Member ID<input minLength={2} maxLength={60} value={memberForm.member_code} onChange={e=>setMemberForm({...memberForm,member_code:e.target.value})} required/></label><label>Full name<input minLength={2} maxLength={160} value={memberForm.name} onChange={e=>setMemberForm({...memberForm,name:e.target.value})} required/></label><label>Mobile number<input type="tel" minLength={7} maxLength={20} pattern="[0-9+() -]{7,20}" value={memberForm.mobile} onChange={e=>setMemberForm({...memberForm,mobile:e.target.value})} required/></label><label>Joining date<input type="date" value={memberForm.joining_date} onChange={e=>setMemberForm({...memberForm,joining_date:e.target.value})} required/></label><label className="full">Address<input minLength={3} value={memberForm.address} onChange={e=>setMemberForm({...memberForm,address:e.target.value})} required/></label><label className="full">Notes<input value={memberForm.notes} onChange={e=>setMemberForm({...memberForm,notes:e.target.value})}/></label><button className="wide" disabled={busy}>＋ Add member</button></form></section>}
 <section className="panel"><div className="panel-head"><div><span className="section-kicker">MEMBER DIRECTORY</span><h2>Members in this group</h2><p>Click a member to see their complete payment history and details.</p></div><span className="panel-tag">{groupMembers.length} MEMBERS</span></div><div className="chit-member-grid">{groupMembers.map(m=>{const paid=payments.filter(p=>p.member_id===m.id).reduce((sum,p)=>sum+Number(p.amount||0),0);return <button className="chit-member-card" key={m.id} onClick={()=>setSelectedMemberId(m.id)}><span className="chit-member-avatar">{m.name.slice(0,1).toUpperCase()}</span><span className="chit-member-main"><b>{m.name}</b><small>{m.member_code} · {m.mobile}</small></span><span className="status">{m.status}</span><span className="chit-member-paid">{money(paid)}<small>Loaded payments</small></span><span className="chit-open-link">View details →</span></button>})}{!groupMembers.length&&<p className="empty">No members in this group. Click “Add chit member” to register one.</p>}</div></section>
 <section className="panel"><div className="panel-head"><div><span className="section-kicker">COLLECTION SUMMARY</span><h2>Weekly collection history</h2><p>Full group totals from the backend, including older payments.</p></div>{(role==="owner"||role==="admin")&&<button className="secondary" onClick={()=>download("/api/backup/excel","sujaai-chit-full-export.xlsx")}>Export all data ↓</button>}</div><div className="table-wrap"><table><thead><tr><th>WEEK</th><th>PAYMENT ENTRIES</th><th>COLLECTION</th></tr></thead><tbody>{(groupDetails?.weekly_totals||[]).map(row=><tr key={row.period}><td>{row.period}</td><td>{row.entries}</td><td><b>{money(row.total)}</b></td></tr>)}{!groupDetails?.weekly_totals.length&&<tr><td colSpan={3} className="empty">No payments recorded for this group yet.</td></tr>}</tbody></table></div><div className="chit-total-line"><span>Lifetime group collection</span><strong>{money(total)}</strong></div></section></>})()}
 {selectedGroupId!==null&&selectedMemberId!==null&&(()=>{const g=groups.find(x=>x.id===selectedGroupId);const m=members.find(x=>x.id===selectedMemberId);if(!g||!m)return null;const memberPayments=memberDetails?.payments||payments.filter(p=>p.member_id===m.id);return <><section className="chit-breadcrumb"><button onClick={()=>setSelectedMemberId(null)}>← {g.name}</button><span>/</span><b>{m.name}</b></section><section className="chit-member-hero"><div className="chit-member-avatar large">{m.name.slice(0,1).toUpperCase()}</div><div className="chit-member-hero-copy"><p className="eyebrow">{m.member_code} · {g.name}</p><h2>{m.name}</h2><p>{m.mobile} · Joined {m.joining_date}</p></div><div className="chit-detail-actions"><button className="secondary" onClick={()=>{setEditingMember(m);setMemberEditForm({name:m.name,mobile:m.mobile,address:m.address,joining_date:m.joining_date,notes:m.notes||"",status:m.status});}}>Edit details</button><button className="chit-add-button" onClick={()=>{setPaymentForm({member_id:String(m.id),amount:String(g.default_amount),paid_at:localDateTimeNow(),notes:""});setShowAddPayment(v=>!v);}}>＋ Add payment</button></div></section><section className="mini-stats"><div><span>Total paid</span><b>{money(memberDetails?.lifetime_paid||memberPayments.reduce((sum,p)=>sum+Number(p.amount||0),0))}</b></div><div><span>This week paid</span><b>{money(memberDetails?.current_week_paid||0)}</b></div><div><span>Weeks paid</span><b>{memberDetails?.paid_weeks??0}</b></div><div><span>Payment entries</span><b>{memberDetails?.payment_count??memberPayments.length}</b></div></section>
 {showAddPayment&&<section className="panel chit-form-panel"><div className="panel-head"><div><span className="section-kicker">NEW COLLECTION</span><h2>Record payment for {m.name}</h2><p>Contribution frequency: {g.chit_type} · Suggested amount: {money(g.default_amount)}</p></div><button type="button" className="secondary" onClick={()=>setShowAddPayment(false)}>Close</button></div><form className="form-grid" onSubmit={createPayment}><label>Amount (₹)<input type="number" min="0.01" step="0.01" value={paymentForm.amount} onChange={e=>setPaymentForm({...paymentForm,amount:e.target.value})} required/></label><label>Payment date &amp; time<input type="datetime-local" value={paymentForm.paid_at} onChange={e=>setPaymentForm({...paymentForm,paid_at:e.target.value})} required/></label><label className="full">Notes<input value={paymentForm.notes} onChange={e=>setPaymentForm({...paymentForm,notes:e.target.value})}/></label><button className="wide" disabled={busy||Number(paymentForm.amount)<=0}>＋ Save payment</button></form></section>}
 <section className="panel"><div className="panel-head"><div><span className="section-kicker">PAYMENT HISTORY</span><h2>{m.name} · all payments</h2><p>Each payment keeps its own date, amount, reference and editor history.</p></div><button className="secondary" onClick={()=>download(`/api/chit/members/${m.id}/statement/excel`,`${m.member_code}-statement.xlsx`)}>Export member statement ↓</button></div><div className="table-wrap"><table><thead><tr><th>PAYMENT DATE</th><th>REFERENCE</th><th>FREQUENCY</th><th>AMOUNT</th><th>RECORDED BY</th><th>ACTION</th></tr></thead><tbody>{memberPayments.map(p=><tr key={p.id}><td>{new Date(p.paid_at).toLocaleString("en-IN")}</td><td><b>{p.payment_ref}</b></td><td>{p.frequency}</td><td><b>{money(p.amount)}</b></td><td>{p.recorded_by}</td><td><div className="row-actions"><button className="small-btn" onClick={()=>download(`/api/chit/payments/${p.id}/pdf`,`${p.payment_ref}.pdf`)}>Receipt</button><button className="small-btn" onClick={()=>{setEditing(p);setEditForm({amount:p.amount,paid_at:toLocalDateTimeInput(p.paid_at),notes:p.notes||""});setOwnerPassword("");}}>Edit payment</button></div></td></tr>)}{!memberPayments.length&&<tr><td colSpan={6} className="empty">No payment entries for this member yet.</td></tr>}</tbody></table></div></section>
 <section className="panel"><div className="panel-head"><div><span className="section-kicker">WEEK-BY-WEEK RECORD</span><h2>Paid weeks</h2><p>Weeks with at least one recorded contribution.</p></div></div><div className="table-wrap"><table><thead><tr><th>WEEK</th><th>PAYMENT ENTRIES</th><th>TOTAL PAID</th></tr></thead><tbody>{(memberDetails?.weekly_totals||[]).map(row=><tr key={row.period}><td>{row.period}</td><td>{row.entries}</td><td><b>{money(row.total)}</b></td></tr>)}{!memberDetails?.weekly_totals.length&&<tr><td colSpan={3} className="empty">No weekly payment history yet.</td></tr>}</tbody></table></div></section></>})()}
 </>}
 {page==="reports"&&<><section className="page-intro"><div><p className="eyebrow">BUSINESS INTELLIGENCE</p><h2>Collection reports</h2><p>Explore period-wise totals and group-level collection performance.</p></div><div className="page-intro-badge"><strong>{money(reportSummary?.total_collection||summary?.total_collection||0)}</strong><span>Current report total</span></div></section><section className="panel"><div className="panel-head"><div><span className="section-kicker">REPORT BUILDER</span><h2>Collection performance</h2><p>Choose a grouping and date range to refresh these totals.</p></div><span className="panel-tag">LIVE DATA</span></div><div className="report-filters"><label>Grouping<select value={period} onChange={e=>setPeriod(e.target.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label><label>From<input type="date" value={reportStart} onChange={e=>setReportStart(e.target.value)}/></label><label>To<input type="date" value={reportEnd} onChange={e=>setReportEnd(e.target.value)}/></label><button onClick={()=>loadPeriod().catch(e=>setNotice(e.message))}>Apply filters</button></div><div className="stats report-stats"><article className="stat-card"><p>Total collection</p><strong>{money(reportSummary?.total_collection||0)}</strong></article><article className="stat-card"><p>Payments</p><strong>{reportSummary?.payment_count||0}</strong></article><article className="stat-card"><p>Active members</p><strong>{members.filter(m=>m.status==="active").length}</strong></article><article className="stat-card"><p>Active groups</p><strong>{groups.filter(g=>g.status==="active").length}</strong></article></div><div className="report-chart"><div className="report-chart-heading"><div><b>Collection trend</b><small>Visual summary of the selected periods</small></div><span>{periodRows.length} periods</span></div>{periodRows.length?<div className="report-bars">{periodRows.slice(-10).map(row=>{const max=Math.max(1,...periodRows.map(x=>Number(x.total||0)));const amount=Number(row.total||0);return <div className="report-bar-item" key={row.period}><div className="report-bar-value">{money(amount)}</div><div className="report-bar-track"><span style={{height:`${Math.max(amount?6:2,(amount/max)*100)}%`}}></span></div><small>{row.period}</small></div>})}</div>:<p className="empty">Apply a date range with records to see the collection trend.</p>}</div><div className="table-wrap"><table><thead><tr><th>PERIOD</th><th>PAYMENTS</th><th>COLLECTION</th></tr></thead><tbody>{periodRows.map(r=><tr key={r.period}><td>{r.period}</td><td>{r.entries}</td><td><b>{money(r.total)}</b></td></tr>)}{!periodRows.length&&<tr><td colSpan={3} className="empty">No records for this period.</td></tr>}</tbody></table></div></section><section className="panel"><div className="panel-head"><div><h2>Collection by group</h2></div></div><div className="report-group-breakdown">{groups.map(g=>{const total=Number(reportSummary?.group_totals.find(x=>x.group_name===g.name)?.collection||0);const max=Math.max(1,...(reportSummary?.group_totals||[]).map(x=>Number(x.collection||0)));return <div className="report-group-row" key={g.id}><div className="collection-meta"><div><b>{g.name}</b><small>{g.group_code} · {g.chit_type}</small></div><strong>{money(total)}</strong></div><div className="collection-track"><span style={{width:`${Math.max(total?2:0,(total/max)*100)}%`}}></span></div></div>})}</div></section></>}
 {page==="backup"&&(role==="owner"||role==="admin")&&<><section className="page-intro"><div><p className="eyebrow">DATA & GOVERNANCE</p><h2>Backup and activity history</h2><p>Export your records, restore an eligible backup and review recent audit events.</p></div><div className="page-intro-badge"><strong>{auditRows.length}</strong><span>Recent audit events</span></div></section><section className="panel"><div className="panel-head"><div><span className="section-kicker">EXPORT CENTER</span><h2>Download your data</h2><p>Keep a separate, secure copy of financial and member records.</p></div></div><div className="backup-actions"><article><span className="stat-icon green">XLS</span><h3>Excel workbook</h3><p>Summary, groups, members and payment sheets.</p><button onClick={()=>download("/api/backup/excel","sujaai-chit-backup.xlsx")}>Download Excel</button></article><article><span className="stat-icon blue">JSON</span><h3>JSON backup</h3><p>Structured data backup for controlled restoration.</p><button onClick={()=>download("/api/backup/json","sujaai-backup.json")}>Download JSON</button></article></div></section>{role==="owner"&&<section className="panel"><div className="panel-head"><div><span className="section-kicker">OWNER TOOL</span><h2>Restore a JSON backup</h2><p>Restoration is allowed only when the chit tables are empty. Download a backup before proceeding.</p></div></div><label className="file-drop">Choose a SUJAAI JSON backup<input type="file" accept="application/json,.json" onChange={e=>importBackup(e.target.files?.[0])}/></label></section>}<section className="panel"><div className="panel-head"><div><span className="section-kicker">SECURITY TRAIL</span><h2>Audit history</h2><p>Recent changes to users, groups, members, payments and backups.</p></div></div><button className="secondary" onClick={()=>download("/api/audit","sujaai-audit.json")}>Download audit data</button><div className="table-wrap audit-table"><table><thead><tr><th>TIME</th><th>USER</th><th>ACTION</th><th>RECORD</th><th>DETAILS</th></tr></thead><tbody>{auditRows.map(row=><tr key={row.id}><td>{new Date(row.created_at).toLocaleString("en-IN")}</td><td>{row.actor}</td><td>{row.action}</td><td>{row.entity_type} · {row.entity_id}</td><td>{row.details}</td></tr>)}{!auditRows.length&&<tr><td colSpan={5} className="empty">No audit events yet.</td></tr>}</tbody></table></div><p className="tiny">Audit events are read-only and available to owners and administrators.</p></section></>}
 {page==="resume"&&<ResumeDesigner request={request}/>}
 {page==="pvc"&&<PvcDesigner request={request}/>}
 {page==="users"&&(role==="owner"||role==="admin")&&<><section className="page-intro"><div><p className="eyebrow">WORKSPACE ADMINISTRATION</p><h2>Team and access control</h2><p>Create staff or administrator accounts and deactivate access when required.</p></div><div className="page-intro-badge"><strong>{users.length}</strong><span>Team accounts</span></div></section><section className="mini-stats"><div><span>Owner accounts</span><b>{users.filter(u=>u.role==="owner").length}</b></div><div><span>Administrators</span><b>{users.filter(u=>u.role==="admin").length}</b></div><div><span>Staff accounts</span><b>{users.filter(u=>u.role==="staff").length}</b></div><div><span>Active accounts</span><b>{users.filter(u=>u.is_active).length}</b></div></section><section className="panel"><div className="panel-head"><div><span className="section-kicker">INVITE TEAM</span><h2>Create a team account</h2><p>Choose a unique email address and a strong temporary password.</p></div><span className="form-step">01 / ACCESS</span></div><form className="form-grid" onSubmit={createStaff}><label>Email<input type="email" value={newUser.email} onChange={e=>setNewUser({...newUser,email:e.target.value})} required/></label><label>Temporary password<input type="password" minLength={12} value={newUser.password} onChange={e=>setNewUser({...newUser,password:e.target.value})} required/></label><label>Role<select value={newUser.role} onChange={e=>setNewUser({...newUser,role:e.target.value})}><option value="staff">Staff</option><option value="admin">Admin</option></select></label><button className="wide" disabled={busy}>＋ Create account</button></form></section><section className="panel"><div className="panel-head"><div><span className="section-kicker">ACCOUNT DIRECTORY</span><h2>Manage team access</h2><p>Deactivate accounts without deleting their audit history.</p></div><span className="panel-tag">{users.filter(u=>u.is_active).length} ACTIVE</span></div><div className="table-wrap"><table><thead><tr><th>EMAIL</th><th>ROLE</th><th>CREATED</th><th>STATUS</th><th>ACTION</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td>{u.email}</td><td>{u.role}</td><td>{new Date(u.created_at).toLocaleDateString("en-IN")}</td><td>{u.is_active?"Active":"Inactive"}</td><td><button className="small-btn" onClick={()=>toggleUser(u)}>{u.is_active?"Deactivate":"Activate"}</button></td></tr>)}</tbody></table></div></section></>}
 <footer>SUJAAI · Chit Management <span>Financial records remain in your configured database.</span></footer>
 </main>
 {editingGroup&&<div className="modal-backdrop"><form className="modal-card" onSubmit={saveGroupEdit}><div className="panel-head"><div><h2>Edit chit group</h2><p>{editingGroup.group_code}</p></div><button type="button" className="secondary" onClick={()=>setEditingGroup(null)}>×</button></div><label>Group name<input value={groupEditForm.name} onChange={e=>setGroupEditForm({...groupEditForm,name:e.target.value})} required/></label><label>Frequency<select value={groupEditForm.chit_type} onChange={e=>setGroupEditForm({...groupEditForm,chit_type:e.target.value})}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label><label>Contribution (₹)<input type="number" min="0.01" step="0.01" value={groupEditForm.default_amount} onChange={e=>setGroupEditForm({...groupEditForm,default_amount:e.target.value})} required/></label><label>Start date<input type="date" value={groupEditForm.start_date} onChange={e=>setGroupEditForm({...groupEditForm,start_date:e.target.value})} required/></label><label>Description<input value={groupEditForm.description} onChange={e=>setGroupEditForm({...groupEditForm,description:e.target.value})}/></label><label>Status<select value={groupEditForm.status} onChange={e=>setGroupEditForm({...groupEditForm,status:e.target.value})}><option value="active">Active</option><option value="paused">Paused</option><option value="completed">Completed</option></select></label><div className="modal-actions"><button type="button" className="secondary" onClick={()=>setEditingGroup(null)}>Cancel</button><button disabled={busy}>Save group</button></div></form></div>}
 {editingMember&&<div className="modal-backdrop"><form className="modal-card" onSubmit={saveMemberEdit}><div className="panel-head"><div><h2>Edit member</h2><p>{editingMember.member_code}</p></div><button type="button" className="secondary" onClick={()=>setEditingMember(null)}>×</button></div><label>Full name<input value={memberEditForm.name} onChange={e=>setMemberEditForm({...memberEditForm,name:e.target.value})} required/></label><label>Mobile<input value={memberEditForm.mobile} onChange={e=>setMemberEditForm({...memberEditForm,mobile:e.target.value})} required/></label><label>Address<input value={memberEditForm.address} onChange={e=>setMemberEditForm({...memberEditForm,address:e.target.value})} required/></label><label>Joining date<input type="date" value={memberEditForm.joining_date} onChange={e=>setMemberEditForm({...memberEditForm,joining_date:e.target.value})} required/></label><label>Notes<input value={memberEditForm.notes} onChange={e=>setMemberEditForm({...memberEditForm,notes:e.target.value})}/></label><label>Status<select value={memberEditForm.status} onChange={e=>setMemberEditForm({...memberEditForm,status:e.target.value})}><option value="active">Active</option><option value="inactive">Inactive</option></select></label><div className="modal-actions"><button type="button" className="secondary" onClick={()=>setEditingMember(null)}>Cancel</button><button disabled={busy}>Save member</button></div></form></div>}
 {editing&&<div className="modal-backdrop"><form className="modal-card" onSubmit={saveCorrection}><div className="panel-head"><div><h2>Edit payment</h2><p>{editing.payment_ref} · all changes are audited</p></div><button type="button" className="secondary" onClick={()=>setEditing(null)}>×</button></div><label>Amount (₹)<input type="number" min="0.01" step="0.01" value={editForm.amount} onChange={e=>setEditForm({...editForm,amount:e.target.value})} required/></label><label>Payment date &amp; time<input type="datetime-local" value={editForm.paid_at} onChange={e=>setEditForm({...editForm,paid_at:e.target.value})} required/></label><label>Notes<input value={editForm.notes} onChange={e=>setEditForm({...editForm,notes:e.target.value})}/></label>{(localDateKey(editing.paid_at)!==localDateKey(new Date())||localDateKey(editForm.paid_at)!==localDateKey(new Date()))&&<label>Owner approval password<input type="password" value={ownerPassword} onChange={e=>setOwnerPassword(e.target.value)} autoComplete="current-password" required/><small>Past or future date corrections need the owner’s ADMIN_PASSWORD approval.</small></label>}<div className="modal-actions"><button type="button" className="secondary" onClick={()=>setEditing(null)}>Cancel</button><button disabled={busy}>Save correction</button></div></form></div>}
 </div>;
}
