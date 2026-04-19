import React, { useMemo, useState } from "react";

type Task = { id:number; title:string; status:string; priority?:string; assignee_agent_id?:number|null; updated_at?:string };

const STATUSES = ["open","in_progress","completed","blocked","cancelled"] as const;
const LABEL: Record<string,string> = { open:"Open", in_progress:"In Progress", completed:"Completed", blocked:"Blocked", cancelled:"Cancelled" };

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [result, setResult] = useState<string>("No result yet.");
  const [budget, setBudget] = useState<string>("No budget loaded.");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [dragTask, setDragTask] = useState<{id:number; from:string} | null>(null);

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [title, setTitle] = useState("Plan launch campaign");
  const [description, setDescription] = useState("");
  const [assignee, setAssignee] = useState("");
  const [priority, setPriority] = useState("medium");
  const [recurringId, setRecurringId] = useState("");
  const [intervalMinutes, setIntervalMinutes] = useState("60");
  const [oauthAppName, setOauthAppName] = useState("HelmiesAI-Agent");
  const [oauthRequestUrl, setOauthRequestUrl] = useState("https://example.com/gateway/inbound");
  const [oauthRedirect, setOauthRedirect] = useState("https://example.com/slack/oauth/callback");
  const [modelAgentId, setModelAgentId] = useState("");
  const [modelProvider, setModelProvider] = useState("openai");
  const [modelName, setModelName] = useState("gpt-4.1-mini");
  const [modelBaseUrl, setModelBaseUrl] = useState("");

  const headers = useMemo(() => {
    const h: Record<string,string> = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  }, [token]);

  async function api(path: string, method = "GET", body?: unknown) {
    const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const txt = await res.text();
    let data: any = {};
    try { data = txt ? JSON.parse(txt) : {}; } catch { data = { raw: txt }; }
    if (!res.ok) throw data;
    return data;
  }

  async function login() {
    try {
      const d = await api("/auth/login", "POST", { username, password });
      setToken(d.access_token);
      setResult(JSON.stringify(d, null, 2));
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function loadBudget() {
    try { setBudget(JSON.stringify(await api("/execution/budget/effective"), null, 2)); }
    catch (e:any) { setBudget(JSON.stringify(e, null, 2)); }
  }

  async function createTask() {
    try {
      const d = await api("/workforce/tasks", "POST", {
        title, description,
        assignee_agent_id: assignee ? Number(assignee) : null,
        collaborator_agent_ids: [], priority,
      });
      setResult(JSON.stringify(d, null, 2));
      await refreshKanban();
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function refreshKanban() {
    try {
      const d = await api("/workforce/tasks");
      setTasks(d.tasks || []);
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function moveTask(taskId:number, to:string) {
    try {
      const d = await api(`/workforce/tasks/${taskId}/status`, "POST", { status: to });
      setResult(JSON.stringify(d, null, 2));
      await refreshKanban();
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function runRecurringNow() {
    try { setResult(JSON.stringify(await api("/workforce/recurring/run_once", "POST"), null, 2)); await refreshKanban(); }
    catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function createRecurring() {
    try {
      const d = await api("/workforce/recurring", "POST", {
        title, description,
        assignee_agent_id: assignee ? Number(assignee) : null,
        collaborator_agent_ids: [],
        priority,
        interval_minutes: Number(intervalMinutes || "60"),
        auto_run: false,
        enabled: true,
        start_immediately: true,
      });
      setRecurringId(String(d.recurring_id || ""));
      setResult(JSON.stringify(d, null, 2));
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function startSlackOAuth() {
    try {
      const d = await api("/workforce/slack/oauth/start", "POST", {
        app_name: oauthAppName,
        request_url: oauthRequestUrl,
        redirect_urls: [oauthRedirect],
        command_name: "/helmies",
      });
      setResult(JSON.stringify(d, null, 2));
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function simulateSlackCallback() {
    try {
      const started = await api("/workforce/slack/oauth/start", "POST", {
        app_name: oauthAppName,
        request_url: oauthRequestUrl,
        redirect_urls: [oauthRedirect],
        command_name: "/helmies",
      });
      const d = await api("/workforce/slack/oauth/callback", "POST", {
        state: started.state,
        code: "simulated-code",
        team_id: "T-simulated",
        team_name: "Simulated Team",
        app_id: "A-simulated",
        bot_user_id: "U-simulated",
        access_token: "xoxb-simulated",
        scope: "chat:write,commands",
      });
      setResult(JSON.stringify({started, callback:d}, null, 2));
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function listSlackInstalls() {
    try { setResult(JSON.stringify(await api("/workforce/slack/installations"), null, 2)); }
    catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  async function updateAgentModel() {
    try {
      const id = Number(modelAgentId);
      if (!Number.isInteger(id)) throw { error: "Set valid agent ID" };
      const d = await api(`/workforce/agents/${id}/model`, "POST", {
        model_provider: modelProvider || null,
        model_name: modelName || null,
        model_base_url: modelBaseUrl || null,
      });
      setResult(JSON.stringify(d, null, 2));
    } catch (e:any) { setResult(JSON.stringify(e, null, 2)); }
  }

  return (
    <div className="app">
      <h1>HelmiesAgents Admin</h1>
      <div className="card">
        <h3>Auth</h3>
        <div className="row">
          <input value={username} onChange={e=>setUsername(e.target.value)} placeholder="username" />
          <input value={password} onChange={e=>setPassword(e.target.value)} placeholder="password" />
        </div>
        <button onClick={login}>Login</button>
      </div>

      <div className="card" data-testid="budget-panel">
        <h3>Effective Budget</h3>
        <button onClick={loadBudget}>Load Effective Budget</button>
        <pre>{budget}</pre>
      </div>

      <div className="card">
        <h3>Workforce Control Center</h3>
        <div className="row3">
          <input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Task title" />
          <input value={assignee} onChange={e=>setAssignee(e.target.value)} placeholder="Assignee Agent ID" />
          <select value={priority} onChange={e=>setPriority(e.target.value)}>
            <option value="low">low</option><option value="medium">medium</option><option value="high">high</option><option value="urgent">urgent</option>
          </select>
        </div>
        <textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="Task description" />
        <div className="row">
          <button onClick={createTask}>Create Task</button>
          <button onClick={refreshKanban}>Refresh Kanban</button>
        </div>

        <h4>Recurring</h4>
        <div className="row3">
          <input value={intervalMinutes} onChange={e=>setIntervalMinutes(e.target.value)} placeholder="Interval minutes" />
          <input value={recurringId} onChange={e=>setRecurringId(e.target.value)} placeholder="Recurring ID" />
          <button onClick={createRecurring}>Create Recurring</button>
        </div>
        <button onClick={runRecurringNow}>Run Recurring Now</button>

        <h4>Slack OAuth Wizard</h4>
        <div className="row3">
          <input value={oauthAppName} onChange={e=>setOauthAppName(e.target.value)} placeholder="App name" />
          <input value={oauthRequestUrl} onChange={e=>setOauthRequestUrl(e.target.value)} placeholder="Request URL" />
          <input value={oauthRedirect} onChange={e=>setOauthRedirect(e.target.value)} placeholder="Redirect URL" />
        </div>
        <div className="row">
          <button onClick={startSlackOAuth}>Start Slack OAuth</button>
          <button onClick={simulateSlackCallback}>Simulate OAuth Callback</button>
        </div>
        <button onClick={listSlackInstalls}>List Slack Installs</button>

        <h4>Per-agent model settings</h4>
        <div className="row3">
          <input value={modelAgentId} onChange={e=>setModelAgentId(e.target.value)} placeholder="Agent ID" />
          <input value={modelProvider} onChange={e=>setModelProvider(e.target.value)} placeholder="Provider" />
          <input value={modelName} onChange={e=>setModelName(e.target.value)} placeholder="Model" />
        </div>
        <input value={modelBaseUrl} onChange={e=>setModelBaseUrl(e.target.value)} placeholder="Base URL" />
        <button onClick={updateAgentModel}>Update Agent Model Settings</button>
      </div>

      <div className="card">
        <h3>Kanban</h3>
        <div className="kanban">
          {STATUSES.map((s)=> {
            const items = tasks.filter(t => t.status === s);
            return (
              <div
                key={s}
                className="col"
                onDragOver={(e)=>{ e.preventDefault(); e.currentTarget.classList.add('drag-over'); }}
                onDragLeave={(e)=> e.currentTarget.classList.remove('drag-over')}
                onDrop={async (e)=> {
                  e.preventDefault();
                  e.currentTarget.classList.remove('drag-over');
                  if (!dragTask || dragTask.from === s) return;
                  await moveTask(dragTask.id, s);
                  setDragTask(null);
                }}
              >
                <h4>{LABEL[s]} ({items.length})</h4>
                {items.map(t => (
                  <div
                    key={t.id}
                    className="task"
                    draggable
                    onDragStart={()=> setDragTask({id:t.id, from:s})}
                  >
                    <div><b>#{t.id}</b> {t.title}</div>
                    <div style={{opacity:.75,fontSize:12}}>priority={t.priority || '-'} assignee={t.assignee_agent_id ?? '-'}</div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      <div className="card">
        <h3>Result</h3>
        <pre>{result}</pre>
      </div>
    </div>
  );
}
