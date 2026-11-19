import { FormEvent, useCallback, useEffect, useState } from "react";

type Group = { id: number; group_code: string; name: string; chit_type: string; default_amount: string; start_date: string; status: string };
type Summary = { total_collection: string; payment_count: number; group_totals: { group_name: string; collection: string }[] };
type Member = { id: number; member_code: string; group_id: number; name: string; mobile: string; address: string; joining_date: string; status: string };
const API = (import.meta as any).env.VITE_API_BASE_URL || "";

export default function App() {
  const [token, setToken] = useState(sessionStorage.getItem("sujaai_token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [groups, setGroups] = useState<Group[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<number | "">("");
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [groupForm, setGroupForm] = useState({ group_code: "", name: "", chit_type: "monthly", default_amount: "", start_date: new Date().toISOString().slice(0, 10), description: "" });
  const [memberForm, setMemberForm] = useState({ member_code: "", name: "", mobile: "", address: "", joining_date: new Date().toISOString().slice(0, 10) });
  const [paymentForm, setPaymentForm] = useState({ member_id: "", amount: "", paid_at: new Date().toISOString().slice(0, 16) });

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const response = await fetch(API + path, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } });
    if (response.status === 401) { sessionStorage.removeItem("sujaai_token"); setToken(""); throw new Error("Session expired. Please sign in again."); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Request failed");
    return data;
  }, [token]);

  const refresh = useCallback(async () => {
    const [g, s, m] = await Promise.all([request("/api/chit/groups"), request("/api/chit/reports/summary"), request("/api/chit/members")]);
    setGroups(g); setSummary(s); setMembers(m);
  }, [request]);

  useEffect(() => { if (token) refresh().catch(e => setNotice(e.message)); }, [token, refresh]);

  async function signIn(e: FormEvent) {
    e.preventDefault(); setBusy(true); setNotice("");
    try {
      const res = await fetch(API + "/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
      const data = await res.json(); if (!res.ok) throw new Error(data.detail || "Sign in failed");
      sessionStorage.setItem("sujaai_token", data.access_token); setToken(data.access_token); setPassword("");
    } catch (e) { setNotice((e as Error).message); } finally { setBusy(false); }
  }

  async function createGroup(e: FormEvent) {
    e.preventDefault(); setBusy(true); setNotice("");
    try { await request("/api/chit/groups", { method: "POST", body: JSON.stringify({ ...groupForm, default_amount: Number(groupForm.default_amount) }) }); setGroupForm({ group_code: "", name: "", chit_type: "monthly", default_amount: "", start_date: new Date().toISOString().slice(0, 10), description: "" }); await refresh(); setNotice("Group created successfully."); }
    catch (e) { setNotice((e as Error).message); } finally { setBusy(false); }
  }

  async function createMember(e: FormEvent) {
    e.preventDefault(); if (!selectedGroup) return; setBusy(true); setNotice("");
    try { await request("/api/chit/members", { method: "POST", body: JSON.stringify({ ...memberForm, group_id: selectedGroup }) }); setMemberForm({ member_code: "", name: "", mobile: "", address: "", joining_date: new Date().toISOString().slice(0, 10) }); await refresh(); setNotice("Member added successfully."); }
    catch (e) { setNotice((e as Error).message); } finally { setBusy(false); }
  }

  async function createPayment(e: FormEvent) {
    e.preventDefault(); const member = members.find(m => m.id === Number(paymentForm.member_id)); if (!member) return;
    const group = groups.find(g => g.id === member.group_id); if (!group) return;
    setBusy(true); setNotice("");
    try { await request("/api/chit/payments", { method: "POST", body: JSON.stringify({ member_id: member.id, amount: paymentForm.amount, paid_at: new Date(paymentForm.paid_at).toISOString(), frequency: group.chit_type }) }); setPaymentForm({ member_id: "", amount: "", paid_at: new Date().toISOString().slice(0, 16) }); await refresh(); setNotice("Payment recorded successfully."); }
    catch (e) { setNotice((e as Error).message); } finally { setBusy(false); }
  }

  const visibleMembers = members.filter(m => (!selectedGroup || m.group_id === selectedGroup) && [m.name, m.member_code, m.mobile].some(v => v.toLowerCase().includes(search.toLowerCase())));
  const money = (v: string | number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(v || 0));

  if (!token) return <main className="login-shell"><section className="login-card"><div className="brand-mark">S</div><p className="eyebrow">SUJAAI WORKSPACE</p><h1>Welcome back</h1><p className="muted">Sign in to manage your chit groups and collections.</p><form onSubmit={signIn} className="stack"><label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="username" /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password" /></label><button disabled={busy}>{busy ? "Signing in…" : "Sign in securely"}</button></form>{notice && <p className="notice error">{notice}</p>}<p className="tiny">Administrator credentials are configured on the backend.</p></section></main>;

  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">S</div><div><strong>SUJAAI</strong><small>Management Suite</small></div></div><div className="nav-label">WORKSPACE</div><a className="nav-item active" href="#dashboard">▦ <span>Dashboard</span></a><a className="nav-item" href="#groups">▧ <span>Groups</span></a><a className="nav-item" href="#members">♙ <span>Members</span></a><a className="nav-item" href="#payments">₹ <span>Payments</span></a><div className="sidebar-bottom"><div className="avatar">A</div><div className="profile"><strong>Administrator</strong><small>Owner workspace</small></div><button className="signout" onClick={() => { sessionStorage.removeItem("sujaai_token"); setToken(""); }}>↪</button></div></aside>
    <main className="main" id="dashboard"><header className="topbar"><div><p className="eyebrow">OVERVIEW</p><h1>Chit dashboard</h1></div><button className="secondary" onClick={() => refresh().catch(e => setNotice(e.message))}>↻ Refresh</button></header>
      {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      <section className="stats"><article className="stat-card"><span className="stat-icon green">₹</span><p>Total collection</p><strong>{money(summary?.total_collection || 0)}</strong><small>Based on saved payments</small></article><article className="stat-card"><span className="stat-icon blue">▦</span><p>Chit groups</p><strong>{groups.length}</strong><small>Registered groups</small></article><article className="stat-card"><span className="stat-icon violet">♙</span><p>Total members</p><strong>{members.length}</strong><small>Across all groups</small></article><article className="stat-card"><span className="stat-icon amber">↗</span><p>Payment entries</p><strong>{summary?.payment_count || 0}</strong><small>Saved transactions</small></article></section>
      <section className="content-grid" id="groups"><article className="panel"><div className="panel-head"><div><h2>Create a chit group</h2><p>Set up a new daily, weekly or monthly group.</p></div></div><form className="form-grid" onSubmit={createGroup}><label>Group ID<input value={groupForm.group_code} onChange={e => setGroupForm({ ...groupForm, group_code: e.target.value })} placeholder="e.g. G1" required /></label><label>Group name<input value={groupForm.name} onChange={e => setGroupForm({ ...groupForm, name: e.target.value })} placeholder="Group name" required /></label><label>Frequency<select value={groupForm.chit_type} onChange={e => setGroupForm({ ...groupForm, chit_type: e.target.value })}><option value="monthly">Monthly</option><option value="weekly">Weekly</option><option value="daily">Daily</option></select></label><label>Contribution (₹)<input type="number" min="0.01" step="0.01" value={groupForm.default_amount} onChange={e => setGroupForm({ ...groupForm, default_amount: e.target.value })} required /></label><label>Start date<input type="date" value={groupForm.start_date} onChange={e => setGroupForm({ ...groupForm, start_date: e.target.value })} required /></label><label>Description<input value={groupForm.description} onChange={e => setGroupForm({ ...groupForm, description: e.target.value })} /></label><button className="wide" disabled={busy}>＋ Create group</button></form></article>
      <article className="panel"><div className="panel-head"><div><h2>Add a member</h2><p>Register a member under an existing group.</p></div></div><form className="form-grid" onSubmit={createMember}><label className="full">Chit group<select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value ? Number(e.target.value) : "")} required><option value="">Choose a group</option>{groups.map(g => <option key={g.id} value={g.id}>{g.group_code} — {g.name}</option>)}</select></label><label>Member ID<input value={memberForm.member_code} onChange={e => setMemberForm({ ...memberForm, member_code: e.target.value })} placeholder="e.g. G1-M001" required /></label><label>Full name<input value={memberForm.name} onChange={e => setMemberForm({ ...memberForm, name: e.target.value })} required /></label><label>Mobile number<input value={memberForm.mobile} onChange={e => setMemberForm({ ...memberForm, mobile: e.target.value })} required /></label><label>Joining date<input type="date" value={memberForm.joining_date} onChange={e => setMemberForm({ ...memberForm, joining_date: e.target.value })} required /></label><label className="full">Address<input value={memberForm.address} onChange={e => setMemberForm({ ...memberForm, address: e.target.value })} required /></label><button className="wide" disabled={busy || !groups.length}>＋ Add member</button></form></article></section>
      <section className="panel" id="payments"><div className="panel-head"><div><h2>Record a payment</h2><p>Payment frequency is inherited from the member’s chit group.</p></div></div><form className="form-grid" onSubmit={createPayment}><label>Member<select value={paymentForm.member_id} onChange={e => setPaymentForm({ ...paymentForm, member_id: e.target.value })} required><option value="">Choose a member</option>{members.map(m => <option key={m.id} value={m.id}>{m.member_code} — {m.name}</option>)}</select></label><label>Amount (₹)<input type="number" min="0.01" step="0.01" value={paymentForm.amount} onChange={e => setPaymentForm({ ...paymentForm, amount: e.target.value })} required /></label><label>Payment date &amp; time<input type="datetime-local" value={paymentForm.paid_at} onChange={e => setPaymentForm({ ...paymentForm, paid_at: e.target.value })} required /></label><button className="wide" disabled={busy || !members.length}>＋ Save payment</button></form></section>
      <section className="panel table-panel" id="members"><div className="panel-head"><div><h2>Members</h2><p>Search by member name, ID or mobile number.</p></div><div className="table-tools"><input placeholder="⌕ Search members…" value={search} onChange={e => setSearch(e.target.value)} /><select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value ? Number(e.target.value) : "")}><option value="">All groups</option>{groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div></div><div className="table-wrap"><table><thead><tr><th>MEMBER</th><th>MEMBER ID</th><th>MOBILE</th><th>GROUP</th><th>STATUS</th></tr></thead><tbody>{visibleMembers.map(m => <tr key={m.id}><td><strong>{m.name}</strong></td><td>{m.member_code}</td><td>{m.mobile}</td><td>{groups.find(g => g.id === m.group_id)?.name || "—"}</td><td><span className="status">{m.status}</span></td></tr>)}{!visibleMembers.length && <tr><td colSpan={5} className="empty">No members found. Add a member to get started.</td></tr>}</tbody></table></div></section>
      <section className="panel"><div className="panel-head"><div><h2>Group collection summary</h2><p>Totals are calculated from saved payment records.</p></div></div><div className="group-list">{groups.map(g => <div className="group-row" key={g.id}><div className="group-symbol">▦</div><div className="group-info"><strong>{g.name}</strong><small>{g.group_code} · {g.chit_type} · {money(g.default_amount)} contribution</small></div><span className="status">{g.status}</span><strong>{money(summary?.group_totals.find(x => x.group_name === g.name)?.collection || 0)}</strong></div>)}{!groups.length && <p className="empty">Your groups will appear here after creation.</p>}</div></section>
      <footer>SUJAAI · Chit Management foundation <span>Financial totals are derived from database payment entries.</span></footer>
    </main></div>;
}
