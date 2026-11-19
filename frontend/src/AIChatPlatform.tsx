import {useEffect,useRef,useState} from "react";
import type {FormEvent,KeyboardEvent,DragEvent} from "react";
import {ArrowUp,Archive,ChevronDown,Copy,FileText,MessageSquarePlus,MoreHorizontal,Paperclip,PanelLeftClose,PanelLeftOpen,Pin,Plus,RefreshCw,Search,Send,Settings2,ShieldCheck,Square,ThumbsDown,ThumbsUp,Trash2,X} from "lucide-react";

type RequestFn=<T>(path:string,options?:RequestInit)=>Promise<T>;
type ChatModel={id:string;name:string;description:string;available:boolean;version:string};
type ChatItem={id:number;title:string;pinned:boolean;archived:boolean;updated_at:string};
type Message={id:number;role:"user"|"assistant";content:string;sources:{source:string;chunk_id:number;score:number}[]};
export default function AIChatPlatform({request}:{request:RequestFn}){
 const [chats,setChats]=useState<ChatItem[]>([]),[active,setActive]=useState<number|null>(null),[messages,setMessages]=useState<Message[]>([]);
 const [models,setModels]=useState<ChatModel[]>([]),[model,setModel]=useState("auto"),[draft,setDraft]=useState(""),[search,setSearch]=useState("");
 const [loading,setLoading]=useState(false),[streaming,setStreaming]=useState(false),[error,setError]=useState(""),[sidebar,setSidebar]=useState(true),[archived,setArchived]=useState(false),[files,setFiles]=useState<File[]>([]),[status,setStatus]=useState("");
 const [dark,setDark]=useState(false),[font,setFont]=useState("normal"),[showSettings,setShowSettings]=useState(false);
 const scrollRef=useRef<HTMLDivElement>(null),abortRef=useRef<AbortController|null>(null),fileRef=useRef<HTMLInputElement>(null);
 const apiBase=String(import.meta.env.VITE_API_BASE_URL||"/api").trim().replace(/\/+$/,"");
 const token=()=>localStorage.getItem("sujaai_token")||"";
 async function loadChats(){try{const rows=await request<ChatItem[]>("ai/conversations?archived="+archived);setChats(rows);}catch(e){setError(e instanceof Error?e.message:"Unable to load chat history");}}
 async function loadModels(){try{setModels(await request<ChatModel[]>("ai/models"));}catch(e){setError(e instanceof Error?e.message:"Unable to load models");}}
 useEffect(()=>{void loadChats();void loadModels();},[archived]);
 useEffect(()=>{if(scrollRef.current)scrollRef.current.scrollTop=scrollRef.current.scrollHeight;},[messages,streaming]);
 async function openChat(id:number){setLoading(true);setError("");try{const data=await request<{messages:Message[]}>("ai/conversations/"+id);setActive(id);setMessages(data.messages);}catch(e){setError(e instanceof Error?e.message:"Unable to open conversation");}finally{setLoading(false);}}
 async function newChat(){abortRef.current?.abort();setStreaming(false);setActive(null);setMessages([]);setDraft("");setFiles([]);setError("");}
 async function createChat(){const c=await request<{id:number}>("ai/conversations",{method:"POST"});setActive(c.id);setMessages([]);await loadChats();return c.id;}
 async function send(e?:FormEvent){e?.preventDefault();const question=draft.trim();if(!question||streaming)return;setError("");setDraft("");setFiles([]);let conversationId=active;
 try{
  if(!conversationId)conversationId=await createChat();
  const userMessage:Message={id:Date.now(),role:"user",content:question,sources:[]};
  const assistantId=Date.now()+1;
  setMessages(prev=>[...prev,userMessage,{id:assistantId,role:"assistant",content:"",sources:[]}]);
  const controller=new AbortController();abortRef.current=controller;setStreaming(true);setStatus("Searching approved insurance knowledge…");
  const response=await fetch(apiBase+"/ai/chat/stream",{method:"POST",headers:{"Content-Type":"application/json",...(token()?{Authorization:"Bearer "+token()}:{})},body:JSON.stringify({question,conversation_id:conversationId,model}),signal:controller.signal});
  if(!response.ok){const d=await response.json().catch(()=>({}));throw new Error(d.detail||"Chat request failed ("+response.status+")");}
  if(!response.body)throw new Error("Streaming is not supported by this browser.");
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="";
  while(true){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});const blocks=buffer.split("\n\n");buffer=blocks.pop()||"";
   for(const block of blocks){const lines=block.split("\n");const event=lines.find(x=>x.startsWith("event:"))?.slice(6).trim();const line=lines.find(x=>x.startsWith("data:"))?.slice(5).trim();if(!line)continue;const data=JSON.parse(line);
    if(event==="meta"){setMessages(prev=>prev.map(m=>m.id===assistantId?{...m,sources:data.sources||[]}:m));setStatus("Preparing a source-grounded answer…");}
    if(event==="token"){setMessages(prev=>prev.map(m=>m.id===assistantId?{...m,content:m.content+data.text}:m));}
   }
  }
  setStatus("");await loadChats();
 }catch(e){if(e instanceof Error&&e.name!=="AbortError")setError(e.message||"Unable to send message");}finally{setStreaming(false);setStatus("");abortRef.current=null;}
 }
 function stop(){abortRef.current?.abort();setStreaming(false);setStatus("Generation stopped.");}
 async function updateChat(id:number,patch:Record<string,unknown>){await request("ai/conversations/"+id,{method:"PATCH",body:JSON.stringify(patch)});await loadChats();}
 async function removeChat(id:number){if(!confirm("Delete this conversation permanently?"))return;await request("ai/conversations/"+id,{method:"DELETE"});if(active===id)newChat();await loadChats();}
 async function uploadFiles(list:FileList|File[]){const allowed=[".pdf",".docx",".txt",".csv",".xlsx",".xlsm"];const chosen=Array.from(list).filter(f=>allowed.some(ext=>f.name.toLowerCase().endsWith(ext)));if(chosen.length!==list.length){setError("Only PDF, DOCX, TXT, CSV and Excel files are supported by the current document extractor.");}for(const file of chosen){const form=new FormData();form.append("file",file);try{setStatus("Uploading "+file.name+"…");await request("ai/documents/upload",{method:"POST",body:form});setFiles(prev=>[...prev,file]);}catch(e){setError(e instanceof Error?e.message:"Upload failed");}}setStatus("");}
 function onDrop(e:DragEvent){e.preventDefault();void uploadFiles(e.dataTransfer.files);}
 async function regenerate(){if(!active||streaming)return;setStreaming(true);try{const r=await request<{answer:string;sources:Message["sources"]}>("ai/chat/regenerate",{method:"POST",body:JSON.stringify({conversation_id:active})});setMessages(prev=>[...prev,{id:Date.now(),role:"assistant",content:r.answer,sources:r.sources}]);}catch(e){setError(e instanceof Error?e.message:"Regeneration failed");}finally{setStreaming(false);}}
 async function feedback(messageId:number,rating:number){if(!active)return;try{await request("ai/feedback",{method:"POST",body:JSON.stringify({conversation_id:active,rating,comment:"Message "+messageId})});setStatus("Feedback saved.");}catch(e){setError(e instanceof Error?e.message:"Feedback failed");}}
 function submitKey(e:KeyboardEvent<HTMLTextAreaElement>){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();void send();}}
 const pinned=chats.filter(c=>c.pinned),recent=chats.filter(c=>!c.pinned);
 return <div className={"suja-chat "+(dark?"dark":"")+" font-"+font} onDragOver={e=>e.preventDefault()} onDrop={onDrop}>
  {sidebar&&<aside className="chat-sidebar"><div className="chat-brand"><span className="chat-brand-mark">S</span><span><b>SUJA</b><small>INSURANCE AI</small></span><button className="chat-plain mobile-close" onClick={()=>setSidebar(false)}><X size={17}/></button></div>
   <button className="chat-new" onClick={()=>void newChat()}><MessageSquarePlus size={17}/> New chat <Plus size={16}/></button>
   <label className="chat-search"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search conversations"/></label>
   <div className="chat-history">
    {pinned.filter(c=>c.title.toLowerCase().includes(search.toLowerCase())).length>0&&<><small className="chat-group-label">PINNED</small>{pinned.filter(c=>c.title.toLowerCase().includes(search.toLowerCase())).map(c=><ChatRow key={c.id} chat={c} active={active===c.id} open={openChat} pin={updateChat} archive={updateChat} remove={removeChat}/>)}</>}
    <small className="chat-group-label">{archived?"ARCHIVED":"RECENT CHATS"}</small>
    {recent.filter(c=>c.title.toLowerCase().includes(search.toLowerCase())).map(c=><ChatRow key={c.id} chat={c} active={active===c.id} open={openChat} pin={updateChat} archive={updateChat} remove={removeChat}/>)}
    {!chats.length&&<p className="chat-empty">Your conversations will appear here.</p>}
   </div>
   <div className="chat-sidebar-bottom"><button onClick={()=>setArchived(v=>!v)}><Archive size={16}/>{archived?"Active chats":"Archived chats"}</button><button onClick={()=>setShowSettings(v=>!v)}><Settings2 size={16}/> Settings</button><div className="chat-profile"><span>S</span><div><b>Workspace admin</b><small>Administrator</small></div></div></div>
  </aside>}
  <main className="chat-main"><header className="chat-top"><button className="chat-plain" onClick={()=>setSidebar(v=>!v)}>{sidebar?<PanelLeftClose size={18}/>:<PanelLeftOpen size={18}/>}</button><div className="chat-model-wrap"><select aria-label="Select AI model" value={model} onChange={e=>setModel(e.target.value)}>{models.map(m=><option key={m.id} value={m.id} disabled={!m.available}>{m.name}{m.available?" · "+m.version:" · unavailable"}</option>)}</select><ChevronDown size={14}/></div><span className="chat-top-label">Insurance intelligence</span><button className="chat-plain" onClick={()=>setShowSettings(v=>!v)}><Settings2 size={17}/></button></header>
   {showSettings&&<div className="chat-settings"><label><input type="checkbox" checked={dark} onChange={e=>setDark(e.target.checked)}/> Dark mode</label><label>Font size <select value={font} onChange={e=>setFont(e.target.value)}><option value="small">Small</option><option value="normal">Normal</option><option value="large">Large</option></select></label><label>Response language <select><option>Auto detect</option><option>Tamil</option><option>English</option><option>Thunglish</option></select></label></div>}
   <div className="chat-scroll" ref={scrollRef}>
    {!messages.length&&!loading?<div className="chat-welcome"><div className="welcome-symbol"><ShieldCheck size={25}/></div><h1>How can I help you today?</h1><p>Your intelligent insurance assistant.</p><div className="chat-suggestions">{["Explain health insurance waiting periods","What documents are needed for a claim?","Explain policy renewal in simple Tamil","Compare approved policy features"].map(q=><button key={q} onClick={()=>setDraft(q)}>{q}<ArrowUp size={14}/></button>)}</div></div>:<div className="chat-messages">{messages.map(m=><article className={"chat-message "+m.role} key={m.id}><div className="message-avatar">{m.role==="assistant"?"S":"A"}</div><div className="message-body"><div className="message-role">{m.role==="assistant"?"SUJA INSURANCE AI":"You"}</div><div className="message-content">{m.content||" "}{m.role==="assistant"&&streaming&&m===messages[messages.length-1]&&<span className="typing-cursor"/>}</div>{m.sources?.length>0&&<div className="message-sources"><b>Sources used</b>{m.sources.map(s=><span key={s.chunk_id}> {s.source} · match {Number(s.score).toFixed(2)}</span>)}</div>}{m.role==="assistant"&&m.content&&<div className="message-actions"><button title="Copy" onClick={()=>void navigator.clipboard.writeText(m.content)}><Copy size={14}/></button><button title="Helpful" onClick={()=>void feedback(m.id,5)}><ThumbsUp size={14}/></button><button title="Not helpful" onClick={()=>void feedback(m.id,1)}><ThumbsDown size={14}/></button>{m===messages[messages.length-1]&&!streaming&&<button title="Regenerate" onClick={()=>void regenerate()}><RefreshCw size={14}/></button>}</div>}</div></article>)}</div>}
   </div>
   <div className="chat-compose-wrap"><div className="chat-disclaimer">SUJA AI uses approved insurance sources. Verify important decisions with an authorized professional.</div>
    {files.length>0&&<div className="chat-attachments">{files.map((f,i)=><span key={i}><FileText size={13}/>{f.name}<button onClick={()=>setFiles(v=>v.filter((_,n)=>n!==i))}><X size={12}/></button></span>)}</div>}
    {status&&<div className="chat-status"><span/> {status}</div>}{error&&<div className="chat-error">{error}<button onClick={()=>setError("")}>Dismiss</button></div>}
    <form className="chat-composer" onSubmit={send}><button type="button" className="chat-attach" title="Attach document" onClick={()=>fileRef.current?.click()}><Paperclip size={19}/></button><input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.csv,.xlsx,.xlsm" onChange={e=>e.target.files&&void uploadFiles(e.target.files)}/><textarea rows={1} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={submitKey} placeholder="Ask anything about insurance…" maxLength={4000}/>{streaming?<button type="button" className="chat-send stop" onClick={stop}><Square size={14}/></button>:<button type="submit" className="chat-send" disabled={!draft.trim()}><Send size={17}/></button>}</form><div className="chat-footnote">Enter to send · Shift + Enter for a new line</div>
   </div>
  </main>
 </div>;
}
function ChatRow({chat,active,open,pin,archive,remove}:{chat:ChatItem;active:boolean;open:(id:number)=>void;pin:(id:number,p:Record<string,unknown>)=>Promise<void>;archive:(id:number,p:Record<string,unknown>)=>Promise<void>;remove:(id:number)=>Promise<void>}){
 const [menu,setMenu]=useState(false);
 return <div className={"chat-row "+(active?"active":"")}><button className="chat-row-open" onClick={()=>void open(chat.id)}><MessageSquarePlus size={14}/><span>{chat.title}</span></button><button className="chat-row-menu" onClick={()=>setMenu(v=>!v)}><MoreHorizontal size={15}/></button>{menu&&<div className="chat-row-pop"><button onClick={()=>{const title=prompt("Conversation name",chat.title);if(title)void pin(chat.id,{title});setMenu(false);}}>Rename</button><button onClick={()=>{void pin(chat.id,{pinned:!chat.pinned});setMenu(false);}}><Pin size={13}/>{chat.pinned?"Unpin":"Pin"}</button><button onClick={()=>{void archive(chat.id,{archived:!chat.archived});setMenu(false);}}><Archive size={13}/>{chat.archived?"Unarchive":"Archive"}</button><button onClick={()=>{void remove(chat.id);setMenu(false);}}><Trash2 size={13}/>Delete</button></div>}</div>;
}
