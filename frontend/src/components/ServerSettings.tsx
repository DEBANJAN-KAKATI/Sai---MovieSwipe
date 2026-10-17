import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { checkServer, getApiBase, normalizeServer, setApiBase } from "../api/base";
import { toast } from "../store";
import { Icon } from "./Icon";

type Status = "checking" | "online" | "offline";

/** Server address + live connection status. Shown in the Android app, where the backend is on another machine. */
export function ServerSettings({ compact = false }: { compact?: boolean }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(getApiBase());
  const [status, setStatus] = useState<Status>("checking");
  const [editing, setEditing] = useState(false);

  const test = async (base: string) => {
    setStatus("checking");
    setStatus((await checkServer(base)) ? "online" : "offline");
  };

  useEffect(() => {
    test(getApiBase());
  }, []);

  const save = async () => {
    const next = normalizeServer(value);
    setApiBase(next);
    setValue(next);
    setEditing(false);
    const ok = await checkServer(next);
    setStatus(ok ? "online" : "offline");
    if (ok) {
      toast("Connected to server");
      qc.invalidateQueries();
    }
  };

  const dot = { checking: "var(--maybe)", online: "var(--yes)", offline: "var(--no)" }[status];
  const label = { checking: "Checking…", online: "Connected", offline: "Can't reach server" }[status];

  return (
    <div className={compact ? "stack" : "panel stack"} style={{ gap: 10 }}>
      <div className="row between">
        <div style={{ minWidth: 0 }}>
          <div className="small muted">Server</div>
          <div className="row" style={{ gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: dot, flex: "none" }} />
            <span className="ellipsis" style={{ fontWeight: 600 }}>
              {getApiBase() || "This website"}
            </span>
          </div>
          <div className="tiny faint">{label}</div>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button className="icon-btn" onClick={() => test(getApiBase())} aria-label="Test connection">
            <Icon name="bolt" size={17} />
          </button>
          <button className="btn sm" onClick={() => setEditing((v) => !v)}>
            Change
          </button>
        </div>
      </div>
      {editing && (
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <input
            className="input"
            inputMode="url"
            autoCapitalize="off"
            autoCorrect="off"
            placeholder="192.168.0.9:8000"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <button className="btn primary">Save</button>
        </form>
      )}
      {status === "offline" && (
        <div className="tiny faint" style={{ lineHeight: 1.5 }}>
          Make sure the sai server is running on your PC with <code>--host 0.0.0.0</code>, your phone is on the
          same Wi-Fi, and Windows Firewall allows port 8000.
        </div>
      )}
    </div>
  );
}
