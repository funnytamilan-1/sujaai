import { useEffect, useMemo, useState } from "react";
import BusinessSuite from "./BusinessSuite";
import AIControlCenter from "./AIControlCenter";
import AIChatPlatform from "./AIChatPlatform";
import type { FormEvent, ReactNode } from "react";
import { Activity, ArrowUpRight, BarChart3, Bell, CheckCircle2, FileSpreadsheet, ImagePlus, LayoutDashboard, LogOut, MessageCircle, Plus, Send, Settings, ShieldCheck, Users, XCircle } from "lucide-react";

type Contact = { id:number; name:string; phone:string; opted_in:boolean };
type Campaign = { id:number; name:string; template_name:string; language:string; image_url:string; body_text:string; status:string; total:number; sent:number; failed:number; created_at:string };
const configuredApiBase = String(import.meta.env.VITE_API_BASE_URL || "/api").trim().replace(/\/+$/, "");
const API = configuredApiBase === "/api" || configuredApiBase.endsWith("/api") ? configuredApiBase : `${configuredApiBase}/api`;
const getToken = () => localStorage.getItem("sujaai_token") || "";

async function request<T>(path:string, options:RequestInit = {}):Promise<T> {
  const headers = new Headers(options.headers || {});
  if (getToken()) headers.set("Authorization", `Bearer ${getToken()}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const endpoint = `${API}/${path.replace(/^\/+/, "")}`;
  const response = await fetch(endpoint, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || `Request failed (${response.status})`);
  return data as T;
}

function Auth({ onLogin }: {onLogin:()=>void}) {
  const [email,setEmail] = useState(""); const [password,setPassword] = useState("");
  const [busy,setBusy] = useState(false); const [error,setError] = useState("");
  async function submit(e:FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const token = await request<{access_token:string}>("/auth/login",{method:"POST",body:JSON.stringify({email,password})});
      localStorage.setItem("sujaai_token",token.access_token); onLogin();
    } catch(err) { setError(err instanceof Error ? err.message : "Something went wrong"); }
    finally { setBusy(false); }
  }
  return <div className="auth-page"><div className="auth-art"><div className="brand-mark">S</div><span className="eyebrow">CAMPAIGN INTELLIGENCE</span><h1>Make every<br/>message count.</h1><p>One calm workspace for your contacts, campaigns and delivery insights.</p><div className="art-bubbles"><span>Excel import</span><span>Image + text</span><span>Delivery insights</span></div></div><form className="auth-card" onSubmit={submit}><div className="brand small"><span className="brand-mark">S</span><b>SUJAAI</b></div><h2>Administrator sign in</h2><p className="muted">Private WhatsApp Campaign Manager</p><label>Email address<input type="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com"/></label><label>Password<input type="password" required minLength={8} value={password} onChange={e=>setPassword(e.target.value)} placeholder="At least 8 characters"/></label>{error&&<div className="error">{error}</div>}<button className="primary full" disabled={busy}>{busy?"Please wait…":"Sign in"}</button><p className="switch">Access is limited to the configured administrator account.</p><p className="tiny">Only the administrator can access this workspace. Keep your credentials secure.</p></form></div>;
}

export default function App() {
  const [authed,setAuthed] = useState(Boolean(getToken()));
  const [page,setPage] = useState("Overview");
  const [contacts,setContacts] = useState<Contact[]>([]);
  const [campaigns,setCampaigns] = useState<Campaign[]>([]);
  const [loading,setLoading] = useState(false);
  const [notice,setNotice] = useState(""); const [error,setError] = useState("");
  const [importFile,setImportFile] = useState<File|null>(null); const [consent,setConsent] = useState(false);
  const [campaignName,setCampaignName] = useState(""); const [template,setTemplate] = useState(""); const [language,setLanguage] = useState("en");
  const [imageUrl,setImageUrl] = useState(""); const [bodyText,setBodyText] = useState(""); const [imageUploading,setImageUploading] = useState(false);
  const [creating,setCreating] = useState(false);
  const optedIn = useMemo(()=>contacts.filter(c=>c.opted_in).length,[contacts]);
  const refresh = async () => {
    setLoading(true); setError("");
    try { const [c,ca] = await Promise.all([request<Contact[]>("/contacts"),request<Campaign[]>("/campaigns")]); setContacts(c); setCampaigns(ca); }
    catch(err) { setError(err instanceof Error?err.message:"Could not load data"); }
    finally { setLoading(false); }
  };
  useEffect(()=>{ if(authed) void refresh(); },[authed]);
  async function importExcel(e:FormEvent) {
    e.preventDefault(); if(!importFile) return;
    const form = new FormData(); form.append("file",importFile);
    try { const result = await request<{added:number;skipped:number;invalid:number}>(`/contacts/import?opted_in=${consent}`,{method:"POST",body:form}); setNotice(`Imported ${result.added} contacts · ${result.skipped} duplicates · ${result.invalid} invalid`); setImportFile(null); await refresh(); }
    catch(err) { setError(err instanceof Error?err.message:"Import failed"); }
  }
  async function uploadCampaignImage(file:File) {
    const form = new FormData();
    form.append("file", file);
    setImageUploading(true);
    setError("");
    try {
      const result = await request<{secure_url:string}>("/media", {method:"POST", body:form});
      setImageUrl(result.secure_url);
      setNotice("Image uploaded successfully.");
    } catch(err) {
      setError(err instanceof Error ? err.message : "Image upload failed");
    } finally {
      setImageUploading(false);
    }
  }
  async function createCampaign(e:FormEvent) {
    e.preventDefault(); setCreating(true); setError(""); setNotice("");
    try { await request("/campaigns",{method:"POST",body:JSON.stringify({name:campaignName,template_name:template,language,image_url:imageUrl,body_text:bodyText})}); setNotice("Campaign saved. Review the template and send when ready."); setCampaignName(""); setTemplate(""); setImageUrl(""); setBodyText(""); await refresh(); }
    catch(err) { setError(err instanceof Error?err.message:"Could not create campaign"); }
    finally { setCreating(false); }
  }
  async function sendCampaign(id:number) {
    if(!confirm("Start this campaign for opted-in contacts? WhatsApp template and account limits apply.")) return;
    try { const r=await request<{message:string}>(`/campaigns/${id}/send`,{method:"POST"}); setNotice(r.message); await refresh(); }
    catch(err) { setError(err instanceof Error?err.message:"Could not start campaign"); }
  }
  async function toggleConsent(c:Contact) {
    try { await request(`/contacts/${c.id}/consent?opted_in=${!c.opted_in}`,{method:"PATCH"}); await refresh(); }
    catch(err) { setError(err instanceof Error?err.message:"Could not update consent"); }
  }
  if(!authed) return <Auth onLogin={()=>setAuthed(true)}/>;
  if(page==="Insurance AI") return <AIChatPlatform request={request}/>;
  const nav = [{name:"Overview",icon:LayoutDashboard},{name:"Contacts",icon:Users},{name:"Import Excel",icon:FileSpreadsheet},{name:"Campaigns",icon:MessageCircle},{name:"Create campaign",icon:Plus},{name:"Business tools",icon:Settings},{name:"Insurance AI",icon:MessageCircle},{name:"AI Control Center",icon:Settings}];
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">S</span><div><b>SUJAAI</b><small>CAMPAIGN MANAGER</small></div></div><div className="workspace"><span className="workspace-dot"/> Personal workspace <span className="chevron">⌄</span></div><span className="nav-label">WORKSPACE</span><nav>{nav.map(n=><button key={n.name} className={page===n.name?"nav-item active":"nav-item"} onClick={()=>setPage(n.name)}><n.icon size={18}/>{n.name}</button>)}</nav><div className="sidebar-bottom"><div className="help-card"><ShieldCheck size={19}/><b>Permission first</b><p>Only message contacts who opted in.</p></div><button className="nav-item" onClick={()=>{localStorage.removeItem("sujaai_token");setAuthed(false);}}><LogOut size={18}/> Sign out</button><div className="profile"><div className="avatar">S</div><div><b>Workspace admin</b><small>Administrator</small></div><Settings size={17}/></div></div></aside><main className="main"><header className="topbar"><div><span className="crumb">Workspace /</span> <b>{page}</b></div><div className="top-actions"><span className="status-pill"><i/> API workspace</span><button className="icon-btn" title="Notifications"><Bell size={18}/></button><div className="avatar">S</div></div></header><div className="content"><div className="page-heading"><div><span className="eyebrow">YOUR BUSINESS, IN SYNC</span><h1>{page==="Overview"?"Good morning.":page}</h1><p>{page==="Overview"?"A clear view of your contacts and campaign activity.":"Manage your opted-in contacts and WhatsApp campaigns."}</p></div><button className="secondary" disabled={loading} onClick={()=>void refresh()}><Activity size={16}/> {loading?"Refreshing…":"Refresh"}</button></div>{notice&&<div className="success"><CheckCircle2 size={17}/>{notice}<button onClick={()=>setNotice("")}><XCircle size={16}/></button></div>}{error&&<div className="error"><XCircle size={17}/>{error}<button onClick={()=>setError("")}>Dismiss</button></div>}
{page==="Overview"&&<><div className="stat-grid"><Stat icon={<Users/>} label="Total contacts" value={contacts.length.toLocaleString()} hint="Imported contacts"/><Stat icon={<ShieldCheck/>} label="Opted-in contacts" value={optedIn.toLocaleString()} hint="Eligible for campaigns"/><Stat icon={<Send/>} label="Campaigns" value={campaigns.length.toLocaleString()} hint="Created campaigns"/><Stat icon={<BarChart3/>} label="Messages sent" value={campaigns.reduce((n,c)=>n+c.sent,0).toLocaleString()} hint="Reported by API"/></div><div className="panel-grid"><section className="panel"><div className="panel-head"><div><h3>Recent campaigns</h3><p>Your latest campaign activity</p></div><button className="text-btn" onClick={()=>setPage("Campaigns")}>View all <ArrowUpRight size={15}/></button></div><CampaignTable campaigns={campaigns.slice(0,5)} onSend={sendCampaign}/></section><section className="panel quick-panel"><div className="panel-head"><div><h3>Quick actions</h3><p>Keep your workflow moving</p></div></div><button className="quick-action" onClick={()=>setPage("Import Excel")}><span className="quick-icon green"><FileSpreadsheet/></span><span><b>Import contacts</b><small>Upload an Excel spreadsheet</small></span><ArrowUpRight size={16}/></button><button className="quick-action" onClick={()=>setPage("Create campaign")}><span className="quick-icon purple"><ImagePlus/></span><span><b>Create a campaign</b><small>Prepare image + text template</small></span><ArrowUpRight size={16}/></button><div className="note"><ShieldCheck size={17}/><span><b>Built for responsible messaging</b><small>Consent is checked before campaign sending.</small></span></div></section></div></>}
{page==="Import Excel"&&<section className="panel form-panel"><div className="panel-head"><div><h3>Import contacts from Excel</h3><p>Upload .xlsx or .xlsm. We detect the Mobile / Phone column automatically.</p></div><FileSpreadsheet className="panel-symbol"/></div><form onSubmit={importExcel}><label className="dropzone"><FileSpreadsheet size={30}/><b>{importFile?importFile.name:"Choose an Excel file"}</b><span>Excel workbook · up to 8 MB</span><input type="file" accept=".xlsx,.xlsm" onChange={e=>setImportFile(e.target.files?.[0]||null)}/></label><label className="check-row"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I confirm these contacts have explicitly agreed to receive WhatsApp messages from this business.</label><p className="hint">Only select this if you have actually collected and recorded permission. Existing contacts are not overwritten.</p><button className="primary" disabled={!importFile}><FileSpreadsheet size={17}/> Import contacts</button></form></section>}
{page==="Contacts"&&<section className="panel"><div className="panel-head"><div><h3>Contact directory</h3><p>{contacts.length} contacts · {optedIn} opted in</p></div><button className="primary small-btn" onClick={()=>setPage("Import Excel")}><Plus size={16}/> Import</button></div><div className="table-wrap"><table><thead><tr><th>NAME</th><th>MOBILE</th><th>CONSENT</th><th>ACTION</th></tr></thead><tbody>{contacts.map(c=><tr key={c.id}><td><b>{c.name||"Unnamed contact"}</b></td><td>{c.phone}</td><td><span className={c.opted_in?"badge good":"badge neutral"}>{c.opted_in?"Opted in":"Not opted in"}</span></td><td><button className="text-btn" onClick={()=>void toggleConsent(c)}>{c.opted_in?"Revoke":"Mark consent"}</button></td></tr>)}</tbody></table>{!contacts.length&&<Empty text="No contacts yet. Import an Excel file to get started."/>}</div></section>}
{page==="Create campaign"&&<section className="panel form-panel"><div className="panel-head"><div><h3>New WhatsApp campaign</h3><p>Use an approved WhatsApp template with an IMAGE header and BODY parameter.</p></div><ImagePlus className="panel-symbol"/></div><form onSubmit={createCampaign} className="campaign-form"><label>Campaign name<input required maxLength={160} value={campaignName} onChange={e=>setCampaignName(e.target.value)} placeholder="November customer update"/></label><div className="two-col"><label>Approved template name<input required pattern="[A-Za-z0-9_]+" value={template} onChange={e=>setTemplate(e.target.value)} placeholder="your_approved_template"/></label><label>Template language<input required value={language} onChange={e=>setLanguage(e.target.value)} placeholder="en"/></label></div><label>Upload campaign image<input type="file" accept="image/png,image/jpeg,image/webp" disabled={imageUploading} onChange={e=>{const file=e.target.files?.[0];if(file) void uploadCampaignImage(file);}}/>{imageUploading&&<small>Uploading image…</small>}</label><label>Public HTTPS image URL<input required type="url" pattern="https://.+" value={imageUrl} onChange={e=>setImageUrl(e.target.value)} placeholder="https://your-domain.com/poster.jpg"/></label><label>Body text parameter<textarea maxLength={1024} rows={4} value={bodyText} onChange={e=>setBodyText(e.target.value)} placeholder="Text value for the first BODY template parameter (if your template uses one)"/></label><div className="note"><ShieldCheck size={18}/><span><b>Before sending</b><small>Meta must have approved the template. The image URL must be publicly accessible over HTTPS. Only opted-in contacts are targeted.</small></span></div><button className="primary" disabled={creating}>{creating?"Saving…":"Save campaign"} <ArrowUpRight size={16}/></button></form></section>}
{page==="Business tools"&&<BusinessSuite request={request}/>}{page==="AI Control Center"&&<AIControlCenter request={request}/>}
{page==="Campaigns"&&<section className="panel"><div className="panel-head"><div><h3>Campaign history</h3><p>Review and launch your prepared campaigns</p></div><button className="primary small-btn" onClick={()=>setPage("Create campaign")}><Plus size={16}/> New campaign</button></div><CampaignTable campaigns={campaigns} onSend={sendCampaign}/>{!campaigns.length&&<Empty text="No campaigns yet. Create your first campaign."/>}</section>}
<div className="footer-note">SUJAAI · Secure campaign workspace <span>Messages are sent through Meta WhatsApp Business Platform.</span></div></div></main></div>;
}

function Stat({icon,label,value,hint}:{icon:ReactNode;label:string;value:string;hint:string}) { return <div className="stat-card"><div className="stat-top"><span>{label}</span><i>{icon}</i></div><strong>{value}</strong><small>{hint}</small></div>; }
function Empty({text}:{text:string}) { return <div className="empty"><MessageCircle size={24}/><p>{text}</p></div>; }
function CampaignTable({campaigns,onSend}:{campaigns:Campaign[];onSend:(id:number)=>void}) {
 return <div className="table-wrap"><table><thead><tr><th>CAMPAIGN</th><th>STATUS</th><th>RECIPIENTS</th><th>SENT</th><th>FAILED</th><th>ACTION</th></tr></thead><tbody>{campaigns.map(c=><tr key={c.id}><td><b>{c.name}</b><small className="sub-cell">{c.template_name}</small></td><td><span className={c.status==="completed"?"badge good":c.status==="sending"?"badge live":"badge neutral"}>{c.status}</span></td><td>{c.total}</td><td>{c.sent}</td><td>{c.failed}</td><td><button className="text-btn" disabled={c.status==="sending"||c.status==="completed"} onClick={()=>onSend(c.id)}>Send <ArrowUpRight size={14}/></button></td></tr>)}</tbody></table></div>;
}
