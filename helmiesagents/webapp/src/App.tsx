import React, { useMemo, useState } from "react";

type Task = { id:number; title:string; status:string; priority?:string; assignee_agent_id?:number|null; updated_at?:string };
type DemoScreen = { id:number; name:string; xKm:number; yKm:number };

const STATUSES = ["open","in_progress","completed","blocked","cancelled"] as const;
const LABEL: Record<string,string> = { open:"Open", in_progress:"In Progress", completed:"Completed", blocked:"Blocked", cancelled:"Cancelled" };
const MAP_RANGE_KM = 8;

const PROFESSIONAL_AGENT_PROFILES = [
  {
    name: "Sarah Lind",
    role: "Senior Media Strategist",
    focus: "Campaign structure, channels, budget split",
    avatar: "https://randomuser.me/api/portraits/women/44.jpg",
  },
  {
    name: "Mikael Saari",
    role: "pDOOH Operations Lead",
    focus: "Screen selection, pacing, execution",
    avatar: "https://randomuser.me/api/portraits/men/36.jpg",
  },
  {
    name: "Noora Heikkinen",
    role: "Performance Analyst",
    focus: "Attribution, optimization, reporting",
    avatar: "https://randomuser.me/api/portraits/women/68.jpg",
  },
];

const PDOOH_SCREENS: DemoScreen[] = [
  { id: 1, name: "Trio Entrance", xKm: 0.4, yKm: 0.3 },
  { id: 2, name: "Trio Food Court", xKm: 0.9, yKm: 0.7 },
  { id: 3, name: "Rautatieasema Hall", xKm: -0.8, yKm: 1.1 },
  { id: 4, name: "Aleksanterinkatu North", xKm: 1.2, yKm: -0.4 },
  { id: 5, name: "Aleksanterinkatu South", xKm: -1.3, yKm: -0.9 },
  { id: 6, name: "Market Square East", xKm: 1.7, yKm: 0.6 },
  { id: 7, name: "Market Square West", xKm: -1.6, yKm: 0.8 },
  { id: 8, name: "Mukkula Junction", xKm: 2.0, yKm: -1.1 },
  { id: 9, name: "Asemantausta Link", xKm: -2.1, yKm: 0.9 },
  { id: 10, name: "Paavola Bridge", xKm: 2.3, yKm: 1.2 },
  { id: 11, name: "Ankkuri Route", xKm: -2.4, yKm: -0.8 },
  { id: 12, name: "Kiverio Corner", xKm: 0.6, yKm: 2.6 },
  { id: 13, name: "Karisto Main Rd", xKm: -0.7, yKm: -2.7 },
  { id: 14, name: "Möysä Bus Hub", xKm: 2.8, yKm: -0.5 },
  { id: 15, name: "Nastola Connector", xKm: -2.9, yKm: 0.4 },
  { id: 16, name: "Renkomäki Gateway", xKm: 1.5, yKm: 2.5 },
  { id: 17, name: "Hennala Front", xKm: -1.4, yKm: 2.6 },
  { id: 18, name: "Kauppakatu Mid", xKm: 2.7, yKm: 1.7 },
  { id: 19, name: "Harju Lane", xKm: -2.5, yKm: -1.8 },
  { id: 20, name: "Sopenkorpi Point", xKm: 1.0, yKm: -3.1 },
  { id: 21, name: "Ahtiala Entry", xKm: -1.1, yKm: 3.0 },
  { id: 22, name: "Laune Crossing", xKm: 3.2, yKm: 0.1 },
  { id: 23, name: "Kytölä Route", xKm: -3.0, yKm: 1.0 },
  { id: 24, name: "Kärpänen North", xKm: 0.2, yKm: 3.4 },
  { id: 25, name: "Kärpänen South", xKm: -0.3, yKm: -3.5 },
  { id: 26, name: "Hiekkanummi", xKm: 4.6, yKm: 1.0 },
  { id: 27, name: "Ala-Okeroinen", xKm: -4.8, yKm: -0.8 },
  { id: 28, name: "Villähde", xKm: 5.1, yKm: 2.2 },
  { id: 29, name: "Nikkilä", xKm: -5.0, yKm: 1.9 },
  { id: 30, name: "Myllypohja", xKm: 4.3, yKm: -2.9 },
  { id: 31, name: "Jalkaranta", xKm: -4.4, yKm: -2.8 },
  { id: 32, name: "Kunnas", xKm: 5.8, yKm: -1.4 },
  { id: 33, name: "Kalliola", xKm: -5.9, yKm: 1.5 },
  { id: 34, name: "Pennala", xKm: 6.3, yKm: 2.4 },
  { id: 35, name: "Orimattila Route", xKm: -6.2, yKm: -2.5 },
];

function distanceKm(xKm:number, yKm:number) {
  return Math.sqrt((xKm * xKm) + (yKm * yKm));
}

function mapPercent(vKm:number) {
  return ((vKm + MAP_RANGE_KM) / (MAP_RANGE_KM * 2)) * 100;
}

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
  const [campaignCenterName, setCampaignCenterName] = useState("Lahti Center");
  const [campaignRadiusKm, setCampaignRadiusKm] = useState(4);

  const availableScreens = useMemo(
    () => PDOOH_SCREENS.filter((s) => distanceKm(s.xKm, s.yKm) <= campaignRadiusKm),
    [campaignRadiusKm],
  );

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
        <h4>Demo Agents</h4>
        <div className="agentGrid">
          {PROFESSIONAL_AGENT_PROFILES.map((agent) => (
            <div className="agentCard" key={agent.name}>
              <img src={agent.avatar} alt={agent.name} className="agentAvatar" />
              <div>
                <div className="agentName">{agent.name}</div>
                <div className="agentRole">{agent.role}</div>
                <div className="agentFocus">{agent.focus}</div>
              </div>
            </div>
          ))}
        </div>

        <h4>Campaign Creation Map (pDOOH Radius)</h4>
        <div className="row3">
          <input
            value={campaignCenterName}
            onChange={(e)=>setCampaignCenterName(e.target.value)}
            placeholder="Campaign center"
          />
          <div className="stack">
            <label>Radius: {campaignRadiusKm.toFixed(1)} km</label>
            <input
              type="range"
              min={1}
              max={8}
              step={0.5}
              value={campaignRadiusKm}
              onChange={(e)=>setCampaignRadiusKm(Number(e.target.value))}
            />
          </div>
          <div className="availablePdooh">
            <div className="bigCount">{availableScreens.length}</div>
            <div>pDOOH screens available</div>
          </div>
        </div>

        <div className="mapWrap" role="img" aria-label="pDOOH screens map">
          <div
            className="radiusCircle"
            style={{
              width: `${(campaignRadiusKm / MAP_RANGE_KM) * 100}%`,
              height: `${(campaignRadiusKm / MAP_RANGE_KM) * 100}%`,
            }}
          />
          <div className="mapCenter" title={campaignCenterName}>●</div>
          {PDOOH_SCREENS.map((screen) => {
            const inside = distanceKm(screen.xKm, screen.yKm) <= campaignRadiusKm;
            return (
              <span
                key={screen.id}
                className={`screenPin ${inside ? "inside" : "outside"}`}
                title={`${screen.name} (${inside ? "inside" : "outside"} radius)`}
                style={{ left: `${mapPercent(screen.xKm)}%`, top: `${mapPercent(-screen.yKm)}%` }}
              />
            );
          })}
        </div>
        <div className="mapSummary">
          {availableScreens.length} pDOOH screens available within {campaignRadiusKm.toFixed(1)} km radius around {campaignCenterName}.
        </div>

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
