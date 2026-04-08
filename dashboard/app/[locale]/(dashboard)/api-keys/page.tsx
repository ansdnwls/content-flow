"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Copy, RotateCw, Trash2, Key, Eye, EyeOff } from "lucide-react";

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used: string | null;
  expires_at: string | null;
}

const DEMO_KEYS: ApiKey[] = [
  {
    id: "1",
    name: "Production",
    prefix: "cf_live_abc1",
    created_at: "2026-03-15",
    last_used: "2026-04-07",
    expires_at: null,
  },
  {
    id: "2",
    name: "Development",
    prefix: "cf_live_xyz2",
    created_at: "2026-04-01",
    last_used: "2026-04-06",
    expires_at: "2026-07-01",
  },
];

export default function ApiKeysPage() {
  const t = useTranslations("api_keys");
  const tc = useTranslations("common");
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);

  function handleCreate() {
    // In production, call API
    setCreatedKey("cf_live_newkey123456789abcdefghijklmn");
    setShowCreate(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={16} /> {t("new_key")}
        </button>
      </div>

      {/* Created key banner */}
      {createdKey && (
        <div className="glass-card p-5 border-accent/30 border">
          <div className="text-sm text-warning mb-2">
            {t("copy_key_warning")}
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-card p-2 rounded-lg text-sm font-mono overflow-x-auto">
              {showKey ? createdKey : "••••••••••••••••••••••••••••••••"}
            </code>
            <button
              onClick={() => setShowKey(!showKey)}
              className="text-muted hover:text-text"
            >
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
            <button
              onClick={() => navigator.clipboard.writeText(createdKey)}
              className="text-muted hover:text-accent"
            >
              <Copy size={16} />
            </button>
          </div>
        </div>
      )}

      {showCreate && (
        <div className="glass-card p-5 space-y-3">
          <label className="block text-sm text-muted">{t("key_name")}</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder={t("key_name_placeholder")}
              className="flex-1"
            />
            <button className="btn-primary" onClick={handleCreate}>
              {tc("create")}
            </button>
          </div>
        </div>
      )}

      {/* Keys list */}
      <div className="space-y-3">
        {DEMO_KEYS.map((k) => (
          <div
            key={k.id}
            className="glass-card p-5 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <Key size={18} className="text-accent" />
              <div>
                <div className="text-sm font-medium">{k.name}</div>
                <div className="text-xs text-muted font-mono">
                  {k.prefix}...
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-xs text-muted text-right">
                <div>{t("created")} {k.created_at}</div>
                {k.last_used && <div>{t("last_used")} {k.last_used}</div>}
              </div>
              <button className="text-muted hover:text-accent-2" title={t("rotate")}>
                <RotateCw size={14} />
              </button>
              <button className="text-muted hover:text-danger" title={tc("delete")}>
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
